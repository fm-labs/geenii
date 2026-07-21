import abc

import hashlib
import json
import inspect
import os
import time
import pickle
import logging
from functools import wraps
from pathlib import Path
from typing import Any, Optional, Callable

import sqlite3

from geenii import config

logger = logging.getLogger(__name__)

class CacheStore(abc.ABC):

    @abc.abstractmethod
    def write_cache(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        pass

    @abc.abstractmethod
    def read_cache(self, key: str) -> Any:
        pass


class SqliteCacheStore(CacheStore):
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
        logger.debug(f"Initializing SqliteCacheStore with db_path={db_path}, timeout={timeout}, busy_timeout_ms={busy_timeout_ms}, wal={wal}, synchronous={synchronous}, cache_size_kib={cache_size_kib}, mmap_size_bytes={mmap_size_bytes}")
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



class FileCacheStore(CacheStore):
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


class InMemoryCacheStore(CacheStore):
    def __init__(self):
        self.store = {}

    def read_cache(self, key: str) -> Any | None:
        entry = self.store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if expiry is not None and time.time() > expiry:
            del self.store[key]
            return None
        return value

    def write_cache(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expiry = None if ttl is None else (time.time() + float(ttl))
        self.store[key] = (expiry, value)


def default_cache_key(func, args, kwargs):
    raw = {"func": func.__name__, "args": args, "kwargs": kwargs}
    logger.debug(">>> Generating cache key for:", raw)
    s = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def default_cache_store():
    try:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        return SqliteCacheStore(f"{config.CACHE_DIR}/cache.sqlite")
    except Exception as e:
        logger.debug(f"Error initializing SqliteCacheStore: {e}")
        logger.debug("Falling back to InMemoryCacheStore (non-persistent, not shared across processes)")
        return InMemoryCacheStore()

CACHE_STORE: CacheStore | None = None

def cache_store():
    global CACHE_STORE
    if CACHE_STORE is None:
        CACHE_STORE = default_cache_store()
    return CACHE_STORE

def _cache_read(func_name: str, key: str) -> tuple[bool, Any]:
    if config.CACHE_DISABLED:
        return False, None
    v = cache_store().read_cache(key)
    if v is not None:
        logger.debug(f"Cache hit for {func_name} with key {key!r}")
        return True, v
    return False, None


def _cache_write(func_name: str, key: str, result: Any, ttl: float | None) -> None:
    if config.CACHE_DISABLED:
        return
    logger.debug(f"Caching result of {func_name} with key {key!r} and ttl {ttl}")
    cache_store().write_cache(key, result, ttl=ttl)


async def acache_fn(func: Callable, key, ttl) -> Any:
    hit, v = _cache_read(func.__name__, key)
    #hit, v = asyncio.to_thread(_cache_read(func.__name__, key))
    if hit:
        return v
    result = await func()
    _cache_write(func.__name__, key, result, ttl)
    #hit, v = asyncio.to_thread(_cache_write(func.__name__, key, result, ttl))
    return result


def cache_fn(func: Callable, key, ttl) -> Any:
    hit, v = _cache_read(func.__name__, key)
    if hit:
        return v
    result = func()
    _cache_write(func.__name__, key, result, ttl)
    return result


def cache_write(key, data, ttl: Optional[int] = None):
    cache_store().write_cache(key, data, ttl=ttl)

def cache_read(key) -> Any:
    return cache_store().read_cache(key)

def cached(ttl=None, cachekey=None):
    def decorator(func):
        is_async = inspect.iscoroutinefunction(func)

        def make_key(args, kwargs) -> str:
            if callable(cachekey):
                return str(cachekey(func, args, kwargs))
            if isinstance(cachekey, str):
                return cachekey
            return default_cache_key(func, args, kwargs)

        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = make_key(args, kwargs)
                return await acache_fn(lambda: func(*args, **kwargs), key, ttl)
            async_wrapper.__wrapped__ = func
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = make_key(args, kwargs)
            return cache_fn(lambda: func(*args, **kwargs), key, ttl)
        sync_wrapper.__wrapped__ = func
        return sync_wrapper

    return decorator
