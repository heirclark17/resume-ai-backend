"""
Web Application Firewall (WAF) Middleware
Detects and blocks common web attacks
"""

import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from typing import Callable, List, Tuple
import os
from app.utils.logger import get_logger

logger = get_logger()


class WAFMiddleware(BaseHTTPMiddleware):
    """Web Application Firewall for request filtering"""

    def __init__(self, app):
        super().__init__(app)
        
        # WAF configuration
        self.enabled = os.getenv("WAF_ENABLED", "true").lower() == "true"
        self.block_mode = os.getenv("WAF_BLOCK_MODE", "true").lower() == "true"
        
        # Compile regex patterns for performance
        self.sql_injection_patterns = self._compile_sql_patterns()
        self.xss_patterns = self._compile_xss_patterns()
        self.path_traversal_patterns = self._compile_path_traversal_patterns()
        
        logger.info(f"WAF middleware initialized (enabled: {self.enabled}, block_mode: {self.block_mode})")

    def _compile_sql_patterns(self) -> List[re.Pattern]:
        """Compile SQL injection detection patterns"""
        patterns = [
            r"(union.*select)",  # UNION SELECT
            r"(select.*from)",  # SELECT FROM
            r"(or\s+1\s*=\s*1)",  # OR 1=1
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_xss_patterns(self) -> List[re.Pattern]:
        """Compile XSS attack detection patterns"""
        patterns = [
            r"<script[^>]*>",  # <script> tags
            r"javascript:",  # javascript: protocol
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _compile_path_traversal_patterns(self) -> List[re.Pattern]:
        """Compile path traversal detection patterns"""
        patterns = [
            r"\.\.\/",  # ../
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _check_patterns(
        self,
        value: str,
        patterns: List[re.Pattern],
        attack_type: str
    ) -> Tuple[bool, str]:
        """Check value against attack patterns"""
        for pattern in patterns:
            if pattern.search(value):
                return True, f"{attack_type}: {pattern.pattern}"
        return False, ""

    async def _scan_request(self, request: Request) -> Tuple[bool, str]:
        """Scan request for malicious patterns"""
        # Check URL path
        path = str(request.url.path)
        
        # Path traversal
        is_attack, reason = self._check_patterns(path, self.path_traversal_patterns, "Path Traversal")
        if is_attack:
            return True, reason

        # Check query parameters
        query_string = str(request.url.query)
        if query_string:
            # SQL injection
            is_attack, reason = self._check_patterns(query_string, self.sql_injection_patterns, "SQL Injection")
            if is_attack:
                return True, reason
            
            # XSS
            is_attack, reason = self._check_patterns(query_string, self.xss_patterns, "XSS")
            if is_attack:
                return True, reason

        return False, ""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through WAF"""
        
        # Skip if WAF disabled
        if not self.enabled:
            return await call_next(request)

        # Scan request
        is_malicious, reason = await self._scan_request(request)

        if is_malicious:
            client_ip = request.client.host if request.client else "unknown"
            log_msg = f"WAF blocked request from {client_ip}: {reason}"
            
            if self.block_mode:
                logger.warning(log_msg)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request blocked by security policy"}
                )
            else:
                logger.warning(f"{log_msg} (LOG-ONLY MODE)")

        return await call_next(request)
