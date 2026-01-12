"""
IP Allowlisting Middleware
Restrict access to admin endpoints based on IP address
"""

from fastapi import Request, HTTPException
from typing import List, Optional
import ipaddress
import os
from app.utils.logger import get_logger

logger = get_logger()


class IPAllowlist:
    """Handle IP-based access control for admin endpoints"""

    def __init__(self):
        # Load allowed IPs from environment variable
        # Format: "192.168.1.1,10.0.0.0/24,2001:db8::/32"
        allowed_ips_str = os.getenv("ADMIN_ALLOWED_IPS", "")
        
        # Parse allowed IP addresses and networks
        self.allowed_networks: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        
        if allowed_ips_str:
            for ip_str in allowed_ips_str.split(","):
                ip_str = ip_str.strip()
                if not ip_str:
                    continue
                
                try:
                    # Try to parse as network (CIDR notation)
                    if "/" in ip_str:
                        network = ipaddress.ip_network(ip_str, strict=False)
                        self.allowed_networks.append(network)
                    else:
                        # Single IP address - convert to /32 or /128 network
                        ip_addr = ipaddress.ip_address(ip_str)
                        if isinstance(ip_addr, ipaddress.IPv4Address):
                            network = ipaddress.IPv4Network(f"{ip_str}/32")
                        else:
                            network = ipaddress.IPv6Network(f"{ip_str}/128")
                        self.allowed_networks.append(network)
                    
                    logger.info(f"Added allowed IP/network: {network}")
                except ValueError as e:
                    logger.error(f"Invalid IP address or network: {ip_str} - {e}")
        
        # Log configuration
        if not self.allowed_networks:
            logger.warning("No admin IP allowlist configured - admin endpoints accessible from any IP")
        else:
            logger.info(f"Admin IP allowlist configured with {len(self.allowed_networks)} entries")

    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if an IP address is in the allowlist

        Args:
            ip_address: IP address to check (IPv4 or IPv6)

        Returns:
            bool: True if allowed, False otherwise
        """
        # If no allowlist configured, allow all (fail open)
        if not self.allowed_networks:
            logger.debug(f"IP {ip_address} allowed (no allowlist configured)")
            return True

        try:
            ip_addr = ipaddress.ip_address(ip_address)
            
            # Check if IP is in any allowed network
            for network in self.allowed_networks:
                if ip_addr in network:
                    logger.debug(f"IP {ip_address} allowed (matches {network})")
                    return True
            
            logger.warning(f"IP {ip_address} blocked (not in allowlist)")
            return False
        
        except ValueError as e:
            logger.error(f"Invalid IP address format: {ip_address} - {e}")
            return False

    def get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request

        Args:
            request: FastAPI request object

        Returns:
            str: Client IP address
        """
        # Check X-Forwarded-For header (set by proxies/load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
            # Take the first one (original client)
            client_ip = forwarded_for.split(",")[0].strip()
            logger.debug(f"Client IP from X-Forwarded-For: {client_ip}")
            return client_ip
        
        # Check X-Real-IP header (set by some proxies)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            logger.debug(f"Client IP from X-Real-IP: {real_ip}")
            return real_ip
        
        # Fall back to direct connection IP
        if request.client:
            client_ip = request.client.host
            logger.debug(f"Client IP from request.client: {client_ip}")
            return client_ip
        
        # Should never happen, but provide default
        logger.warning("Could not determine client IP, using 0.0.0.0")
        return "0.0.0.0"

    async def check_ip_allowlist(self, request: Request) -> None:
        """
        Middleware function to check IP allowlist

        Args:
            request: FastAPI request object

        Raises:
            HTTPException: 403 if IP not allowed
        """
        client_ip = self.get_client_ip(request)
        
        if not self.is_ip_allowed(client_ip):
            logger.warning(f"Access denied for IP {client_ip} to {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail="Access denied: IP address not allowed"
            )


# Singleton instance
_ip_allowlist_instance: Optional[IPAllowlist] = None


def get_ip_allowlist() -> IPAllowlist:
    """Get singleton IPAllowlist instance"""
    global _ip_allowlist_instance
    if _ip_allowlist_instance is None:
        _ip_allowlist_instance = IPAllowlist()
    return _ip_allowlist_instance
