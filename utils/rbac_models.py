"""
RBAC (Role-Based Access Control) data models for the ADG platform.

This module defines the core data structures for user management, authentication,
authorization, and audit logging in the security system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set
import secrets
import uuid

from core.node_interfaces import ValidationResult, ValidationSeverity


class Permission(Enum):
    """Granular permission definitions for system operations."""
    # Directory operations
    DIRECTORY_CREATE = "directory:create"
    DIRECTORY_READ = "directory:read"
    DIRECTORY_UPDATE = "directory:update"
    DIRECTORY_DELETE = "directory:delete"
    DIRECTORY_GENERATE = "directory:generate"
    
    # Workflow management
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_EXECUTE = "workflow:execute"
    
    # AI features
    AI_GENERATE_CONTENT = "ai:generate_content"
    AI_ANALYZE_DATA = "ai:analyze_data"
    AI_OPTIMIZE_WORKFLOW = "ai:optimize_workflow"
    
    # System administration
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    SYSTEM_CONFIG = "system:config"
    AUDIT_READ = "audit:read"
    SECURITY_MANAGE = "security:manage"
    
    # File operations
    FILE_UPLOAD = "file:upload"
    FILE_DOWNLOAD = "file:download"
    FILE_DELETE = "file:delete"
    
    # Template management
    TEMPLATE_CREATE = "template:create"
    TEMPLATE_READ = "template:read"
    TEMPLATE_UPDATE = "template:update"
    TEMPLATE_DELETE = "template:delete"


class Role(Enum):
    """Standard role hierarchy with defined permissions."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class SessionStatus(Enum):
    """Session lifecycle status."""
    ACTIVE = auto()
    EXPIRED = auto()
    REVOKED = auto()
    LOCKED = auto()


class AuthEventType(Enum):
    """Authentication and authorization event types for audit logging."""
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    SESSION_EXPIRED = "auth.session.expired"
    SESSION_REVOKED = "auth.session.revoked"
    PERMISSION_GRANTED = "auth.permission.granted"
    PERMISSION_DENIED = "auth.permission.denied"
    PASSWORD_CHANGED = "auth.password.changed"
    ROLE_ASSIGNED = "auth.role.assigned"
    ROLE_REVOKED = "auth.role.revoked"
    ACCOUNT_LOCKED = "auth.account.locked"
    ACCOUNT_UNLOCKED = "auth.account.unlocked"


# Role permission mappings
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Full system access
        Permission.DIRECTORY_CREATE, Permission.DIRECTORY_READ, Permission.DIRECTORY_UPDATE,
        Permission.DIRECTORY_DELETE, Permission.DIRECTORY_GENERATE,
        Permission.WORKFLOW_CREATE, Permission.WORKFLOW_READ, Permission.WORKFLOW_UPDATE,
        Permission.WORKFLOW_DELETE, Permission.WORKFLOW_EXECUTE,
        Permission.AI_GENERATE_CONTENT, Permission.AI_ANALYZE_DATA, Permission.AI_OPTIMIZE_WORKFLOW,
        Permission.USER_MANAGE, Permission.ROLE_MANAGE, Permission.SYSTEM_CONFIG,
        Permission.AUDIT_READ, Permission.SECURITY_MANAGE,
        Permission.FILE_UPLOAD, Permission.FILE_DOWNLOAD, Permission.FILE_DELETE,
        Permission.TEMPLATE_CREATE, Permission.TEMPLATE_READ, Permission.TEMPLATE_UPDATE,
        Permission.TEMPLATE_DELETE
    },
    Role.OPERATOR: {
        # Operations and workflow management
        Permission.DIRECTORY_CREATE, Permission.DIRECTORY_READ, Permission.DIRECTORY_UPDATE,
        Permission.DIRECTORY_GENERATE,
        Permission.WORKFLOW_CREATE, Permission.WORKFLOW_READ, Permission.WORKFLOW_UPDATE,
        Permission.WORKFLOW_EXECUTE,
        Permission.AI_GENERATE_CONTENT, Permission.AI_ANALYZE_DATA,
        Permission.FILE_UPLOAD, Permission.FILE_DOWNLOAD,
        Permission.TEMPLATE_READ, Permission.TEMPLATE_UPDATE
    },
    Role.VIEWER: {
        # Read-only access
        Permission.DIRECTORY_READ,
        Permission.WORKFLOW_READ,
        Permission.FILE_DOWNLOAD,
        Permission.TEMPLATE_READ
    },
    Role.AUDITOR: {
        # Audit and compliance access
        Permission.DIRECTORY_READ,
        Permission.WORKFLOW_READ,
        Permission.AUDIT_READ,
        Permission.FILE_DOWNLOAD,
        Permission.TEMPLATE_READ
    }
}


@dataclass
class User:
    """User data model with secure password storage and role assignment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    password_hash: str = ""
    salt: str = field(default_factory=lambda: secrets.token_hex(32))
    roles: Set[Role] = field(default_factory=set)
    is_active: bool = True
    is_locked: bool = False
    failed_login_attempts: int = 0
    last_login: Optional[datetime] = None
    last_password_change: datetime = field(default_factory=datetime.utcnow)
    password_expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        if not self.username:
            raise ValueError("Username is required")
        if not self.email:
            raise ValueError("Email is required")
        # Set password expiration to 90 days from creation if not set
        if not self.password_expires_at:
            self.password_expires_at = self.created_at + timedelta(days=90)
    
    def has_role(self, role: Role) -> bool:
        """Check if user has the specified role."""
        return role in self.roles
    
    def add_role(self, role: Role) -> None:
        """Add a role to the user."""
        self.roles.add(role)
        self.updated_at = datetime.utcnow()
    
    def remove_role(self, role: Role) -> None:
        """Remove a role from the user."""
        self.roles.discard(role)
        self.updated_at = datetime.utcnow()
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has the specified permission through their roles."""
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False
    
    def get_all_permissions(self) -> Set[Permission]:
        """Get all permissions granted to the user through their roles."""
        permissions = set()
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        return permissions
    
    def is_password_expired(self) -> bool:
        """Check if the user's password has expired."""
        if not self.password_expires_at:
            return False
        return datetime.utcnow() > self.password_expires_at
    
    def should_lock_account(self, max_failed_attempts: int = 5) -> bool:
        """Check if account should be locked due to failed login attempts."""
        return self.failed_login_attempts >= max_failed_attempts
    
    def reset_failed_attempts(self) -> None:
        """Reset failed login attempts counter."""
        self.failed_login_attempts = 0
        self.updated_at = datetime.utcnow()
    
    def increment_failed_attempts(self) -> None:
        """Increment failed login attempts counter."""
        self.failed_login_attempts += 1
        self.updated_at = datetime.utcnow()
    
    def validate(self) -> List[ValidationResult]:
        """Validate user data."""
        results = []
        
        # Username validation
        if not self.username or len(self.username) < 3:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Username must be at least 3 characters long",
                field_name="username",
                error_code="INVALID_USERNAME"
            ))
        
        # Email validation
        if not self.email or "@" not in self.email:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Valid email address is required",
                field_name="email",
                error_code="INVALID_EMAIL"
            ))
        
        # Role validation
        if not self.roles:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="User has no assigned roles",
                field_name="roles",
                error_code="NO_ROLES"
            ))
        
        return results


@dataclass
class Session:
    """Session data model with security features."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    session_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    csrf_token: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    ip_address: str = ""
    user_agent: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=8))
    last_activity: datetime = field(default_factory=datetime.utcnow)
    activity_timeout: timedelta = field(default_factory=lambda: timedelta(hours=2))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not self.user_id:
            raise ValueError("User ID is required for session")
        if not self.ip_address:
            raise ValueError("IP address is required for session")
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        now = datetime.utcnow()
        return (now > self.expires_at or 
                now > self.last_activity + self.activity_timeout or
                self.status != SessionStatus.ACTIVE)
    
    def is_active(self) -> bool:
        """Check if session is active and valid."""
        return self.status == SessionStatus.ACTIVE and not self.is_expired()
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def revoke(self) -> None:
        """Revoke the session."""
        self.status = SessionStatus.REVOKED
    
    def extend_expiry(self, hours: int = 8) -> None:
        """Extend session expiry time."""
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
    
    def validate_csrf(self, provided_token: str) -> bool:
        """Validate CSRF token."""
        return secrets.compare_digest(self.csrf_token, provided_token)
    
    def validate(self) -> List[ValidationResult]:
        """Validate session data."""
        results = []
        
        if not self.user_id:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="User ID is required",
                field_name="user_id",
                error_code="MISSING_USER_ID"
            ))
        
        if not self.ip_address:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="IP address is required",
                field_name="ip_address",
                error_code="MISSING_IP_ADDRESS"
            ))
        
        if self.is_expired():
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Session has expired",
                field_name="expires_at",
                error_code="SESSION_EXPIRED"
            ))
        
        return results


@dataclass
class AuthEvent:
    """Authentication and authorization event for audit logging."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: AuthEventType = AuthEventType.LOGIN_SUCCESS
    user_id: Optional[str] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: str = ""
    user_agent: str = ""
    resource: Optional[str] = None
    permission: Optional[Permission] = None
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash_chain: Optional[str] = None  # For tamper-proof audit chain
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not self.ip_address:
            raise ValueError("IP address is required for audit event")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "username": self.username,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource": self.resource,
            "permission": self.permission.value if self.permission else None,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "hash_chain": self.hash_chain
        }


@dataclass
class SecurityConfig:
    """Security configuration model."""
    # Password policy
    min_password_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special_chars: bool = True
    password_expiry_days: int = 90
    password_history_count: int = 5
    
    # Account lockout policy
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30
    
    # Session policy
    session_timeout_hours: int = 8
    activity_timeout_hours: int = 2
    max_concurrent_sessions: int = 3
    
    # JWT configuration
    jwt_algorithm: str = "RS256"
    jwt_access_token_expires_minutes: int = 15
    jwt_refresh_token_expires_days: int = 7
    jwt_key_rotation_hours: int = 24
    
    # Rate limiting (requests per hour by role)
    rate_limit_admin: int = 1000
    rate_limit_operator: int = 500
    rate_limit_viewer: int = 100
    rate_limit_auditor: int = 200
    
    # Security features
    enable_csrf_protection: bool = True
    enable_session_fixation_protection: bool = True
    enable_rate_limiting: bool = True
    enable_audit_logging: bool = True
    
    def get_rate_limit_for_role(self, role: Role) -> int:
        """Get rate limit for a specific role."""
        limits = {
            Role.ADMIN: self.rate_limit_admin,
            Role.OPERATOR: self.rate_limit_operator,
            Role.VIEWER: self.rate_limit_viewer,
            Role.AUDITOR: self.rate_limit_auditor
        }
        return limits.get(role, self.rate_limit_viewer)  # Default to viewer limit
    
    def validate(self) -> List[ValidationResult]:
        """Validate security configuration."""
        results = []
        
        if self.min_password_length < 8:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Minimum password length should be at least 8 characters",
                field_name="min_password_length",
                error_code="WEAK_PASSWORD_POLICY"
            ))
        
        if self.max_failed_attempts < 3:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Max failed attempts should be at least 3",
                field_name="max_failed_attempts",
                error_code="WEAK_LOCKOUT_POLICY"
            ))
        
        if self.session_timeout_hours > 24:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Session timeout should not exceed 24 hours",
                field_name="session_timeout_hours",
                error_code="LONG_SESSION_TIMEOUT"
            ))
        
        return results


# Default security configuration
DEFAULT_SECURITY_CONFIG = SecurityConfig()


# Type aliases for better code readability
UserId = str
SessionId = str
TokenString = str
PermissionSet = Set[Permission]
RoleSet = Set[Role]