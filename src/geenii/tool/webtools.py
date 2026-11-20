from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx

from geenii import config
from geenii.tool.common import Tool, ToolCallContext, ToolCallResult

logger = logging.getLogger(__name__)


class _HtmlTextExtractor(HTMLParser):
    """Extract the title and readable text from an HTML document (stdlib only)."""

    _SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
    _BLOCK_TAGS = {
        "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "hr", "main", "nav", "aside",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            self._parts.append(data)

    @property
    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)


class WebFetchTool(Tool):
    """A Tool that fetches data from a web server."""

    NAME = "web_fetch"
    DESCRIPTION = "Fetch data from a web server"
    INPUT_SCHEMA: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "format": "uri", "description": "The url to fetch"},
            "parser": {"type": "string", "description": "The parser to use",
                       "enum": ["none", "json", "html", "xml"], "default": "html"},
        },
        "required": ["url"],
    }

    MAX_REDIRECTS = 3
    TIMEOUT = 30.0
    MAX_CONTENT_BYTES = 5 * 1024 * 1024
    USER_AGENT = "geenii-web-fetch/1.0"

    CACHE_TTL = 3600  # seconds; 0 disables reading from the cache

    def __init__(self, cache_dir: str | None = None, cache_ttl: int | None = None):
        super().__init__(self.NAME, self.DESCRIPTION, self.INPUT_SCHEMA)
        self.cache_ttl = self.CACHE_TTL if cache_ttl is None else cache_ttl
        self.cache_enabled = not config.GEENII_CACHE_DISABLED
        self.cache_dir = cache_dir or os.path.join(config.GEENII_CACHE_DIR, "web_fetch")

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        url = (args.get("url") or "").strip()
        parser = args.get("parser") or "html"

        if not url:
            return ToolCallResult(text="Missing 'url' argument", is_error=True)
        if urlparse(url).scheme not in ("http", "https"):
            return ToolCallResult(text=f"Unsupported url scheme: {url!r} (only http/https)", is_error=True)
        if parser not in ("none", "json", "html", "xml"):
            return ToolCallResult(text=f"Unsupported parser: {parser!r}", is_error=True)

        cached = self._cache_get(url)
        if cached is not None:
            content, meta = cached
            logger.info(f"WebFetchTool [{ctx.id}] cache hit {url}")
        else:
            logger.info(f"WebFetchTool [{ctx.id}] GET {url} parser={parser}")
            try:
                with httpx.Client(
                    follow_redirects=True,
                    max_redirects=self.MAX_REDIRECTS,
                    timeout=self.TIMEOUT,
                    headers={"User-Agent": self.USER_AGENT},
                ) as client:
                    with client.stream("GET", url) as response:
                        content = self._read_limited(response)
            except httpx.TooManyRedirects:
                return ToolCallResult(text=f"Too many redirects (max {self.MAX_REDIRECTS}) for {url}", is_error=True)
            except httpx.HTTPError as e:
                return ToolCallResult(text=f"Request failed for {url}: {e}", is_error=True)
            except ValueError as e:
                return ToolCallResult(text=str(e), is_error=True)

            meta = {
                "url": str(response.url),
                "status_code": response.status_code,
                "reason_phrase": response.reason_phrase,
                "content_type": response.headers.get("content-type", ""),
                "encoding": response.encoding or "utf-8",
                "redirects": [str(r.url) for r in response.history],
                "fetched_at": time.time(),
            }
            if response.is_success:
                self._cache_put(url, content, meta)

        meta = dict(meta)
        #meta["cached"] = cached is not None
        final_url = meta["url"]
        status_code = meta["status_code"]
        reason_phrase = meta.pop("reason_phrase", "")
        text = content.decode(meta.pop("encoding", "utf-8"), errors="replace")

        if status_code >= 400:
            return ToolCallResult(
                text=f"HTTP {status_code} {reason_phrase} for {final_url}\n\n{text[:2000]}",
                structured_content=meta,
                is_error=True,
            )

        try:
            if parser == "json":
                data = json.loads(text)
                meta["data"] = data
                return ToolCallResult(text=json.dumps(data, indent=2, default=str), structured_content=meta)
            if parser == "html":
                extractor = _HtmlTextExtractor()
                extractor.feed(text)
                extractor.close()
                title = " ".join(extractor.title.split())
                meta["title"] = title
                body = extractor.text
                meta["body"] = body
                return ToolCallResult(text=f"# {title}\n\n{body}" if title else body, structured_content=meta)
            if parser == "xml":
                root = ET.fromstring(content)
                ET.indent(root)
                meta["root_tag"] = root.tag
                return ToolCallResult(text=ET.tostring(root, encoding="unicode"), structured_content=meta)
        except (json.JSONDecodeError, ET.ParseError) as e:
            return ToolCallResult(
                text=f"Failed to parse response from {final_url} as {parser}: {e}",
                structured_content=meta,
                is_error=True,
            )

        return ToolCallResult(text=text, structured_content=meta)

    def _cache_paths(self, url: str) -> tuple[str, str]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        base = os.path.join(self.cache_dir, key[:2], key)
        return f"{base}.body", f"{base}.json"

    def _cache_get(self, url: str) -> tuple[bytes, dict[str, Any]] | None:
        if not self.cache_enabled or self.cache_ttl <= 0:
            return None
        body_path, meta_path = self._cache_paths(url)
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            if time.time() - float(meta.get("fetched_at", 0)) > self.cache_ttl:
                return None
            with open(body_path, "rb") as f:
                return f.read(), meta
        except (OSError, ValueError):
            return None

    def _cache_put(self, url: str, content: bytes, meta: dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        body_path, meta_path = self._cache_paths(url)
        try:
            os.makedirs(os.path.dirname(body_path), exist_ok=True)
            # body first, meta last: a meta file only exists once its body is complete
            self._write_atomic(body_path, content)
            self._write_atomic(meta_path, json.dumps({**meta, "request_url": url}).encode("utf-8"))
        except OSError as e:
            logger.warning(f"WebFetchTool: failed to write cache for {url}: {e}")

    @staticmethod
    def _write_atomic(path: str, data: bytes) -> None:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _read_limited(self, response: httpx.Response) -> bytes:
        buf = bytearray()
        for chunk in response.iter_bytes():
            buf.extend(chunk)
            if len(buf) > self.MAX_CONTENT_BYTES:
                raise ValueError(f"Response from {response.url} exceeds {self.MAX_CONTENT_BYTES} bytes")
        return bytes(buf)
