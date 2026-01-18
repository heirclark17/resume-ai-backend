"""
Security Headers Middleware
Adds comprehensive security headers to all HTTP responses
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import os
from app.utils.logger import get_logger

logger = get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    def __init__(self, app):
        super().__init__(app)
        
        # Get configuration from environment
        self.csp_enabled = os.getenv("CSP_ENABLED", "true").lower() == "true"
        self.hsts_enabled = os.getenv("HSTS_ENABLED", "true").lower() == "true"
        
        # Content Security Policy
        self.csp_directives = self._get_csp_directives()
        
        logger.info(f"Security headers middleware initialized (CSP: {self.csp_enabled}, HSTS: {self.hsts_enabled})")

    def _get_csp_directives(self) -> str:
        """
        Build Content Security Policy directives

        Customize based on your application needs.
        Default policy is restrictive for maximum security.
        """
        # Default CSP (strict)
        directives = {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "https://www.google.com", "https://www.gstatic.com"],  # reCAPTCHA
            "style-src": ["'self'", "'unsafe-inline'"],  # Allow inline styles
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'", "data:"],
            "connect-src": ["'self'", "https://www.google.com"],  # reCAPTCHA
            "frame-src": ["'self'", "https://www.google.com"],  # reCAPTCHA
            "object-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "frame-ancestors": ["'none'"],  # Prevent clickjacking
            "upgrade-insecure-requests": []
        }
        
        # Allow custom CSP from environment
        custom_csp = os.getenv("CSP_DIRECTIVES")
        if custom_csp:
            return custom_csp
        
        # Build CSP string
        csp_string = "; ".join([
            f"{directive} {' '.join(sources)}" if sources else directive
            for directive, sources in directives.items()
        ])
        
        return csp_string

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response"""
        
        # Process request
        response = await call_next(request)
        
        # Content Security Policy
        if self.csp_enabled:
            response.headers["Content-Security-Policy"] = self.csp_directives
        
        # HTTP Strict Transport Security (HSTS)
        if self.hsts_enabled:
            # max-age=31536000 (1 year), includeSubDomains, preload
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # X-Frame-Options (prevent clickjacking)
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options (prevent MIME sniffing)
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection (legacy, but still good)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer-Policy (control referrer information)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy (formerly Feature-Policy)
        permissions = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "accelerometer=()",
            "gyroscope=()"
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions)
        
        # Cross-Origin-* policies - Allow for API endpoints
        # Only set these for non-API routes to avoid blocking CORS
        if not request.url.path.startswith("/api/"):
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
            response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        return response
