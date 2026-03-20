"""
Request Logger Middleware for FastAPI

This middleware logs all incoming HTTP requests and their corresponding responses
with detailed information including headers, body, timing, and client info.
"""

from fastapi import Request
import logging
import time
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime


class RequestLoggerMiddleware:
    """
    Middleware that logs all HTTP requests and responses.
    
    Args:
        app: FastAPI application instance
        logger_name: Name for the logger (default: "request_logger")
        log_level: Logging level (default: logging.INFO)
        log_body: Whether to log request/response bodies (default: True)
        log_headers: Whether to log headers (default: True)
        max_body_size: Maximum body size to log in bytes (default: 10000)
        exclude_paths: List of paths to exclude from logging (default: ["/health", "/metrics"])
        sensitive_headers: List of headers to redact (default: ["authorization", "cookie", "x-api-key"])
        log_file: Optional log file path (default: None - logs to console only)
    
    Example:
        app.add_middleware(
            RequestLoggerMiddleware,
            log_body=True,
            log_headers=True,
            max_body_size=5000,
            exclude_paths=["/health", "/docs"],
            log_file="requests.log"
        )
    """
    
    def __init__(
        self,
        app,
        logger_name: str = "request_logger",
        log_level: int = logging.INFO,
        log_body: bool = True,
        log_headers: bool = True,
        max_body_size: int = 10000,
        exclude_paths: Optional[List[str]] = None,
        sensitive_headers: Optional[List[str]] = None,
        log_file: Optional[str] = None
    ):
        self.app = app
        self.log_body = log_body
        self.log_headers = log_headers
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
        self.sensitive_headers = [
            header.lower() for header in (sensitive_headers or [
                "authorization", "cookie", "x-api-key", "x-auth-token"
            ])
        ]
        
        # Setup logger
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(log_level)
        
        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        
        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            self.logger.addHandler(file_handler)
        
        self.logger.addHandler(console_handler)
        
        # Set formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        for handler in self.logger.handlers:
            handler.setFormatter(formatter)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            await self.app(scope, receive, send)
            return

        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Log request
        await self.log_request(request, request_id)
        
        # Capture response
        response_body = b""
        status_code = 200
        response_headers = {}
        
        async def send_wrapper(message):
            nonlocal response_body, status_code, response_headers
            
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = dict(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if self.log_body and len(response_body) < self.max_body_size:
                    response_body += body
            
            await send(message)

        # Process request
        start_time = time.time()
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.error(f"Request {request_id} failed with exception: {str(e)}")
            raise
        finally:
            # Log response
            duration = time.time() - start_time
            await self.log_response(request_id, status_code, response_headers, response_body, duration)

    async def log_request(self, request: Request, request_id: str):
        """Log incoming request details"""
        try:
            # Basic request info
            log_data = {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": self.get_client_ip(request),
                "user_agent": request.headers.get("user-agent", ""),
            }

            # Log headers (with sensitive data filtering)
            if self.log_headers:
                headers = {}
                for name, value in request.headers.items():
                    if name.lower() in self.sensitive_headers:
                        headers[name] = "[REDACTED]"
                    else:
                        headers[name] = value
                log_data["headers"] = headers

            # Log request body
            if self.log_body:
                try:
                    body = await request.body()
                    if body and len(body) <= self.max_body_size:
                        # Try to decode as JSON first
                        try:
                            log_data["body"] = json.loads(body.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # If not JSON, log as string (truncated if too long)
                            body_str = body.decode('utf-8', errors='ignore')
                            log_data["body"] = body_str[:self.max_body_size]
                    elif len(body) > self.max_body_size:
                        log_data["body"] = f"[BODY TOO LARGE: {len(body)} bytes]"
                except Exception as e:
                    log_data["body"] = f"[ERROR READING BODY: {str(e)}]"

            self.logger.info(f"REQUEST {request_id}: {json.dumps(log_data, indent=2)}")
            
        except Exception as e:
            self.logger.error(f"Error logging request {request_id}: {str(e)}")

    async def log_response(
        self, 
        request_id: str, 
        status_code: int, 
        headers: Dict, 
        body: bytes, 
        duration: float
    ):
        """Log response details"""
        try:
            log_data = {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "response_size": len(body)
            }

            # Log response headers
            if self.log_headers and headers:
                # Convert headers from bytes to strings
                str_headers = {}
                for key, value in headers.items():
                    if isinstance(key, bytes):
                        key = key.decode()
                    if isinstance(value, bytes):
                        value = value.decode()
                    str_headers[key] = value
                log_data["headers"] = str_headers

            # Log response body
            if self.log_body and body and len(body) <= self.max_body_size:
                try:
                    # Try to decode as JSON
                    log_data["body"] = json.loads(body.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # If not JSON, log as string
                    body_str = body.decode('utf-8', errors='ignore')
                    log_data["body"] = body_str[:self.max_body_size]
            elif len(body) > self.max_body_size:
                log_data["body"] = f"[RESPONSE TOO LARGE: {len(body)} bytes]"

            # Log level based on status code
            if status_code >= 500:
                self.logger.error(f"RESPONSE {request_id}: {json.dumps(log_data, indent=2)}")
            elif status_code >= 400:
                self.logger.warning(f"RESPONSE {request_id}: {json.dumps(log_data, indent=2)}")
            else:
                self.logger.info(f"RESPONSE {request_id}: {json.dumps(log_data, indent=2)}")

        except Exception as e:
            self.logger.error(f"Error logging response {request_id}: {str(e)}")

    def get_client_ip(self, request: Request) -> str:
        """Extract client IP considering proxy headers"""
        # Check for forwarded headers (common in reverse proxy setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in case of multiple proxies
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
