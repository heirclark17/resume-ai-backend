# IP Allowlisting for Admin Endpoints - Setup Guide

## Overview

IP-based access control restricts admin endpoints to specific IP addresses or networks. This prevents unauthorized access to sensitive administrative functions.

---

## Configuration

Set the ADMIN_ALLOWED_IPS environment variable with comma-separated IP addresses or CIDR networks:

Single IP: ADMIN_ALLOWED_IPS="192.168.1.100"
Multiple IPs: ADMIN_ALLOWED_IPS="192.168.1.100,203.0.113.45"
CIDR networks: ADMIN_ALLOWED_IPS="192.168.1.0/24,10.0.0.0/8"

## Protected Endpoints

GET /api/admin/stats - System statistics
GET /api/admin/users - List all users with pagination
POST /api/admin/users/deactivate - Deactivate user account

## Security Features

- IPv4 and IPv6 support
- CIDR network support
- Proxy header detection (X-Forwarded-For, X-Real-IP)
- Comprehensive logging

## Testing

1. Find your IP: curl https://api.ipify.org
2. Configure: railway variables set ADMIN_ALLOWED_IPS="YOUR_IP"
3. Test access: curl https://your-api.railway.app/api/admin/stats

## Compliance

- CIS Controls v8: Control 4.1, 4.7
- NIST 800-53: AC-3, AC-4
- PCI DSS: Requirement 7, 8.3

**Status:** Implementation Complete
**Last Updated:** 2026-01-11
