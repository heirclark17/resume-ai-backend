"""
Admin Routes - Protected by IP Allowlist
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.resume import BaseResume
from app.middleware.ip_allowlist import get_ip_allowlist
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


# Dependency to check IP allowlist
async def check_admin_ip(request: Request):
    """Verify request comes from allowed IP address"""
    ip_allowlist = get_ip_allowlist()
    await ip_allowlist.check_ip_allowlist(request)


# Response Models
class SystemStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_resumes: int
    total_storage_mb: float
    uptime_hours: float


class UserListItem(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    twofa_enabled: bool
    resume_count: int


class UserListResponse(BaseModel):
    users: List[UserListItem]
    total: int


class UserDeactivateRequest(BaseModel):
    user_id: int
    reason: str


@router.get("/stats", response_model=SystemStatsResponse, dependencies=[Depends(check_admin_ip)])
async def get_system_stats(db: Session = Depends(get_db)):
    """
    Get system statistics (admin only)
    
    Protected by IP allowlist - only accessible from configured admin IPs.
    """
    try:
        # Count total users
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar() or 0
        
        # Count active users
        active_users_result = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users_result.scalar() or 0
        
        # Count total resumes
        total_resumes_result = await db.execute(select(func.count(BaseResume.id)))
        total_resumes = total_resumes_result.scalar() or 0
        
        # Calculate storage (placeholder - would need actual file sizes)
        total_storage_mb = 0.0
        
        # Calculate uptime (placeholder - would track server start time)
        uptime_hours = 0.0
        
        logger.info("Admin accessed system stats")
        
        return SystemStatsResponse(
            total_users=total_users,
            active_users=active_users,
            total_resumes=total_resumes,
            total_storage_mb=total_storage_mb,
            uptime_hours=uptime_hours
        )
    
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system statistics")


@router.get("/users", response_model=UserListResponse, dependencies=[Depends(check_admin_ip)])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all users with statistics (admin only)
    
    Protected by IP allowlist - only accessible from configured admin IPs.
    """
    try:
        # Get users with pagination
        result = await db.execute(
            select(User)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        # Get total count
        total_result = await db.execute(select(func.count(User.id)))
        total = total_result.scalar() or 0
        
        # Get resume counts for each user
        user_list = []
        for user in users:
            # Count resumes for this user
            resume_count_result = await db.execute(
                select(func.count(BaseResume.id)).where(BaseResume.user_id == user.id)
            )
            resume_count = resume_count_result.scalar() or 0
            
            user_list.append(UserListItem(
                id=user.id,
                email=user.email,
                username=user.username,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login,
                twofa_enabled=user.twofa_enabled,
                resume_count=resume_count
            ))
        
        logger.info(f"Admin listed users (skip={skip}, limit={limit})")
        
        return UserListResponse(users=user_list, total=total)
    
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user list")


@router.post("/users/deactivate", dependencies=[Depends(check_admin_ip)])
async def deactivate_user(
    request: UserDeactivateRequest,
    db: Session = Depends(get_db)
):
    """
    Deactivate a user account (admin only)
    
    Protected by IP allowlist - only accessible from configured admin IPs.
    """
    try:
        # Find user
        result = await db.execute(select(User).where(User.id == request.user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Deactivate user
        user.is_active = False
        db.commit()
        
        logger.warning(
            f"Admin deactivated user {user.id} ({user.email}). Reason: {request.reason}"
        )
        
        return {
            "success": True,
            "message": f"User {user.email} deactivated successfully",
            "user_id": user.id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to deactivate user")


# Audit Log Models
class AuditLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    module: str


class AuditLogsResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    format: str


@router.get("/logs", dependencies=[Depends(check_admin_ip)])
async def get_audit_logs(
    limit: int = 100,
    level: str = None,  # DEBUG, INFO, WARNING, ERROR
    format: str = "json"  # json or csv
):
    """
    Export audit logs (admin only)
    
    Protected by IP allowlist.
    
    Query parameters:
    - limit: Number of log entries to return (default: 100, max: 1000)
    - level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
    - format: Output format (json or csv)
    """
    try:
        import os
        from fastapi.responses import PlainTextResponse
        
        # Validate limit
        if limit > 1000:
            limit = 1000
        
        # Get log file path
        log_file = os.path.join("logs", "resume_ai.log")
        
        if not os.path.exists(log_file):
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # Read log file
        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]  # Get last N lines
        
        # Parse log entries
        for line in lines:
            try:
                # Parse log format: YYYY-MM-DD HH:MM:SS - module - LEVEL - message
                parts = line.strip().split(" - ", 3)
                if len(parts) >= 4:
                    timestamp = parts[0]
                    module = parts[1]
                    log_level = parts[2]
                    message = parts[3]
                    
                    # Filter by level if specified
                    if level and log_level != level:
                        continue
                    
                    logs.append({
                        "timestamp": timestamp,
                        "level": log_level,
                        "module": module,
                        "message": message
                    })
            except Exception:
                # Skip malformed log lines
                continue
        
        logger.info(f"Admin exported {len(logs)} audit log entries (format: {format})")
        
        # Return as JSON
        if format.lower() == "json":
            return AuditLogsResponse(
                logs=[AuditLogEntry(**log) for log in logs],
                total=len(logs),
                format="json"
            )
        
        # Return as CSV
        elif format.lower() == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["timestamp", "level", "module", "message"])
            writer.writeheader()
            writer.writerows(logs)
            
            csv_content = output.getvalue()
            output.close()
            
            return PlainTextResponse(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
            )
        
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'json' or 'csv'")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export audit logs")
