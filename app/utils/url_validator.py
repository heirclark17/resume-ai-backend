import re
import ipaddress
from urllib.parse import urlparse
from fastapi import HTTPException


class URLValidator:
    """Validate URLs to prevent SSRF attacks"""

    # Regex patterns for strict validation
    VALID_DOMAIN_PATTERN = re.compile(
        r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'  # Subdomain/domain part
        r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'  # Additional parts
    )

    # Suspicious patterns that indicate attacks
    SUSPICIOUS_PATTERNS = [
        r'%2e%2e',  # URL-encoded directory traversal (..)
        r'%00',      # Null byte injection
        r'%0d',      # Carriage return
        r'%0a',      # Line feed
        r'@',        # Authentication in URL (user:pass@domain)
        r'\\',       # Backslashes (Windows path traversal)
        r'\.\.',     # Directory traversal
        r'file://',  # File protocol
        r'ftp://',   # FTP protocol
        r'data:',    # Data URI scheme
        r'javascript:', # JavaScript protocol
    ]

    # Allowed job board domains (whitelist)
    ALLOWED_DOMAINS = {
        'linkedin.com',
        'www.linkedin.com',
        'indeed.com',
        'www.indeed.com',
        'glassdoor.com',
        'www.glassdoor.com',
        'monster.com',
        'www.monster.com',
        'ziprecruiter.com',
        'www.ziprecruiter.com',
        'careerbuilder.com',
        'www.careerbuilder.com',
        'dice.com',
        'www.dice.com',
        'simplyhired.com',
        'www.simplyhired.com',
        'greenhouse.io',
        'lever.co',
        'workday.com',
        'wd1.myworkdaysite.com',
        'wd5.myworkdaysite.com',
        'myworkday.com',
        'fa.em2.oraclecloud.com',  # Oracle Taleo
        'fa.em3.oraclecloud.com',
        'jpmc.fa.oraclecloud.com',  # JPMorgan
        'careers.microsoft.com',
        'careers.google.com',
        'amazon.jobs',
        'jobs.apple.com',
        'jobs.cisco.com',
        'jobs.oracle.com',
    }

    # Blocked internal/private IP ranges
    BLOCKED_IP_RANGES = [
        ipaddress.ip_network('127.0.0.0/8'),      # Localhost
        ipaddress.ip_network('10.0.0.0/8'),       # Private network
        ipaddress.ip_network('172.16.0.0/12'),    # Private network
        ipaddress.ip_network('192.168.0.0/16'),   # Private network
        ipaddress.ip_network('169.254.0.0/16'),   # Link-local (AWS metadata)
        ipaddress.ip_network('::1/128'),          # IPv6 localhost
        ipaddress.ip_network('fc00::/7'),         # IPv6 private
    ]

    @classmethod
    def validate_job_url(cls, url: str) -> str:
        """
        Validate job URL for SSRF protection

        Args:
            url: The URL to validate

        Returns:
            str: The validated URL

        Raises:
            HTTPException: If URL is invalid or blocked
        """
        if not url or not isinstance(url, str):
            raise HTTPException(status_code=400, detail="Invalid URL: URL is required")

        url = url.strip()

        # Check for suspicious patterns (SSRF attack indicators)
        url_lower = url.lower()
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, url_lower):
                raise HTTPException(
                    status_code=400,
                    detail=f"Blocked URL: Suspicious pattern detected. URLs with special characters or protocols are not allowed."
                )

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid URL: Unable to parse URL")

        # Check scheme (only http/https allowed)
        if parsed.scheme not in ['http', 'https']:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL scheme: '{parsed.scheme}'. Only http and https are allowed"
            )

        # Check if hostname exists
        if not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL: No hostname found")

        hostname = parsed.netloc.lower()

        # Remove port if present
        if ':' in hostname:
            hostname = hostname.split(':')[0]

        # Validate domain format with strict regex
        if not cls.VALID_DOMAIN_PATTERN.match(hostname):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain format: '{hostname}'. Domain must contain only alphanumeric characters, hyphens, and dots."
            )

        # Check for localhost aliases
        localhost_patterns = [
            'localhost',
            '0.0.0.0',
            '127.0.0.1',
            '[::1]',
            '::1'
        ]
        if any(pattern in hostname for pattern in localhost_patterns):
            raise HTTPException(
                status_code=400,
                detail="Blocked URL: Localhost URLs are not allowed for security reasons"
            )

        # Check if hostname is an IP address (block all IPs for safety)
        if cls._is_ip_address(hostname):
            try:
                ip = ipaddress.ip_address(hostname)

                # Check against blocked ranges
                for blocked_range in cls.BLOCKED_IP_RANGES:
                    if ip in blocked_range:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Blocked URL: IP address {hostname} is in a restricted range"
                        )

                # Block all direct IP access for additional security
                raise HTTPException(
                    status_code=400,
                    detail="Blocked URL: Direct IP addresses are not allowed. Please use a domain name."
                )
            except ValueError:
                pass

        # Security check: Block obviously dangerous domains
        # Block domains with suspicious keywords
        blocked_keywords = [
            'internal',
            'admin',
            'api',
            'backend',
            'database',
            'db',
            'staging',
            'test',
            'dev',
            'debug',
        ]

        hostname_parts = hostname.split('.')
        for part in hostname_parts:
            if part.lower() in blocked_keywords:
                raise HTTPException(
                    status_code=400,
                    detail=f"Blocked URL: Domain contains restricted keyword '{part}'"
                )

        # Block domains that are too short (likely malicious)
        if len(hostname) < 4:
            raise HTTPException(
                status_code=400,
                detail=f"Blocked URL: Domain name is suspiciously short"
            )

        # All other security checks passed - allow the URL
        # This is more permissive and allows any legitimate company career site
        return url

    @staticmethod
    def _is_ip_address(hostname: str) -> bool:
        """Check if hostname is an IP address"""
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        # IPv6 pattern (simplified)
        ipv6_pattern = r'^[0-9a-fA-F:]+$'

        return bool(re.match(ipv4_pattern, hostname) or re.match(ipv6_pattern, hostname))
