from functools import wraps
import hashlib
import json
import inspect

import os
import time
import pickle
import hashlib
from pathlib import Path
from typing import Any, Optional

import sqlite3


class SqliteCacheStore:
    """
    SQLite-backed cache with tighter connection PRAGMAs for cross-process use.

    Notes:
      - WAL improves concurrency (many readers + one writer).
      - busy_timeout reduces "database is locked" errors by waiting.
      - synchronous=NORMAL is a common WAL tradeoff (good durability/perf balance).
    """

    def __init__(
        self,
        db_path: str,
        *,
        timeout: float = 5.0,          # sqlite3 connect timeout (seconds)
        busy_timeout_ms: int = 5000,    # PRAGMA busy_timeout (milliseconds)
        wal: bool = True,
        synchronous: str = "NORMAL",    # FULL | NORMAL | OFF
        cache_size_kib: int = -64_000,  # negative => KiB. e.g. -64000 ~= 64MiB
        mmap_size_bytes: int = 128 * 1024 * 1024,  # 128MiB
    ):
        self.conn = sqlite3.connect(
            db_path,
            timeout=timeout,
            check_same_thread=False,
            isolation_level=None,  # autocommit mode (we use explicit BEGIN for writes)
        )

        # Row format + minor ergonomics
        self.conn.row_factory = sqlite3.Row

        # ---- Tightened PRAGMAs ----
        # Use executes for pragmas because parameters aren't accepted for PRAGMA in sqlite
        if wal:
            self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute(f"PRAGMA synchronous={synchronous};")
        self.conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)};")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute(f"PRAGMA cache_size={int(cache_size_kib)};")
        self.conn.execute(f"PRAGMA mmap_size={int(mmap_size_bytes)};")
        self.conn.execute("PRAGMA foreign_keys=ON;")  # not required here, but sane default

        # Optionally helpful in WAL mode; avoids reader blocks on schema changes
        self.conn.execute("PRAGMA recursive_triggers=OFF;")

        # ---- Schema ----
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                expiry REAL,
                value BLOB NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expiry ON cache(expiry)")

    # ---- Internal helper: retry on transient locks ----

    def _with_retry(self, fn, *, retries: int = 3, base_sleep: float = 0.02):
        for i in range(retries + 1):
            try:
                return fn()
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "locked" in msg or "busy" in msg:
                    if i == retries:
                        raise
                    time.sleep(base_sleep * (2 ** i))
                    continue
                raise

    # ---- Public API ----

    def read_cache(self, key: str) -> Any | None:
        now = time.time()

        def op():
            row = self.conn.execute(
                "SELECT expiry, value FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None

            expiry = row["expiry"]
            if expiry is not None and now > expiry:
                # expired → delete
                self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None

            try:
                return pickle.loads(row["value"])
            except Exception:
                # corrupted blob → delete
                self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None

        return self._with_retry(op)

    def write_cache(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expiry = None if ttl is None else (time.time() + float(ttl))
        blob = sqlite3.Binary(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

        def op():
            # IMMEDIATE grabs a RESERVED lock early, reducing lock-upgrade contention in WAL.
            self.conn.execute("BEGIN IMMEDIATE;")
            try:
                self.conn.execute(
                    "INSERT INTO cache(key, expiry, value) VALUES(?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET expiry=excluded.expiry, value=excluded.value",
                    (key, expiry, blob),
                )
                self.conn.execute("COMMIT;")
            except Exception:
                self.conn.execute("ROLLBACK;")
                raise

        self._with_retry(op)

    def purge_expired(self) -> int:
        now = time.time()

        def op():
            self.conn.execute("BEGIN IMMEDIATE;")
            try:
                cur = self.conn.execute(
                    "DELETE FROM cache WHERE expiry IS NOT NULL AND expiry < ?",
                    (now,),
                )
                self.conn.execute("COMMIT;")
                return cur.rowcount
            except Exception:
                self.conn.execute("ROLLBACK;")
                raise

        return self._with_retry(op)

    def close(self) -> None:
        self.conn.close()



class FileCacheStore:
    def __init__(self, directory: str):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.dir / f"{digest}.cache"

    def read_cache(self, key: str) -> Any | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None

        try:
            with path.open("rb") as f:
                expiry, value = pickle.load(f)
        except Exception:
            # corrupted file → treat as miss
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return None

        if expiry is not None and time.time() > expiry:
            # expired
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return None

        return value

    def write_cache(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        path = self._path_for_key(key)
        expiry = None if ttl is None else (time.time() + float(ttl))

        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("wb") as f:
            pickle.dump((expiry, value), f, protocol=pickle.HIGHEST_PROTOCOL)

        # atomic-ish replace
        os.replace(tmp_path, path)


def default_cache_key(func, args, kwargs):
    raw = {"func": func.__name__, "args": args, "kwargs": kwargs}
    print(">>> Generating cache key for:", raw)
    s = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def default_cache_store():
    # return FileCacheStore(".cache")
    return SqliteCacheStore(".cache/cache.sqlite")

def cached(ttl=None, cachekey=None, store=None):
    """
    store must provide: store.read_cache(key), store.write_cache(key, value, ttl=None)
    """

    if store is None:
        #raise ValueError("cached(..., store=...) is required")
        store = default_cache_store()

    def decorator(func):
        is_async = inspect.iscoroutinefunction(func)

        def make_key(args, kwargs):
            if callable(cachekey):
                return cachekey(func, args, kwargs)
            if isinstance(cachekey, str):
                return cachekey
            return default_cache_key(func, args, kwargs)

        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = make_key(args, kwargs)
                v = store.read_cache(key)
                if v is not None:
                    print(f"Cache hit for {func.__name__} with key {key!r}")
                    return v
                result = await func(*args, **kwargs)
                print(f"Caching result of {func.__name__} with key {key!r} and ttl {ttl}")
                store.write_cache(key, result, ttl=ttl)
                return result
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = make_key(args, kwargs)
            v = store.read_cache(key)
            if v is not None:
                print(f"Cache hit for {func.__name__} with key {key!r}")
                return v
            result = func(*args, **kwargs)
            print(f"Caching result of {func.__name__} with key {key!r} and ttl {ttl}")
            store.write_cache(key, result, ttl=ttl)
            return result

        return sync_wrapper

    return decorator
