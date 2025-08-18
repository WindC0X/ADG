"""
Permission checking and authorization utilities for runtime access control.

This module provides centralized permission validation, role-based access control,
and context-aware authorization with comprehensive audit logging.
"""

import logging
from typing import Dict, List, Optional, Set, Any, Callable, Union
from functools import wraps
from contextlib import contextmanager

from .rbac_models import (
    User, Session, Permission, Role, AuthEvent, AuthEventType,
    ROLE_PERMISSIONS
)
from .security_manager import get_security_manager
from .session_manager import get_session_manager

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when authorization checks fail."""
    def __init__(self, message: str, permission: Permission, user_id: Optional[str] = None):
        super().__init__(message)
        self.permission = permission
        self.user_id = user_id


class PermissionChecker:
    """
    Runtime permission validation and role-based access control.
    
    Provides methods for checking permissions, validating access,
    and implementing authorization policies with audit logging.
    """
    
    def __init__(self):
        """Initialize permission checker."""
        self.security_manager = get_security_manager()
        self.session_manager = get_session_manager()
    
    def check_permission(self, user: User, permission: Permission, 
                        resource: Optional[str] = None,
                        context: Optional[Dict[str, Any]] = None,
                        raise_on_failure: bool = False) -> bool:
        """
        Check if user has the specified permission.
        
        Args:
            user: User to check permissions for.
            permission: Permission to check.
            resource: Optional resource being accessed.
            context: Optional context for the permission check.
            raise_on_failure: Whether to raise exception on failure.
            
        Returns:
            True if user has permission, False otherwise.
            
        Raises:
            AuthorizationError: If raise_on_failure is True and check fails.
        """
        if not user.is_active:
            self._log_permission_event(user, permission, False, 
                                     resource, "User account inactive")
            if raise_on_failure:
                raise AuthorizationError("User account is inactive", permission, user.id)
            return False
        
        if user.is_locked:
            self._log_permission_event(user, permission, False, 
                                     resource, "User account locked")
            if raise_on_failure:
                raise AuthorizationError("User account is locked", permission, user.id)
            return False
        
        # Check if user has the permission through their roles
        has_permission = user.has_permission(permission)
        
        # Apply context-specific rules if provided
        if has_permission and context:
            has_permission = self._apply_context_rules(user, permission, context)
        
        # Log the permission check
        self._log_permission_event(user, permission, has_permission, resource)
        
        if not has_permission and raise_on_failure:
            raise AuthorizationError(
                f"User {user.username} does not have permission {permission.value}",
                permission, user.id
            )
        
        return has_permission
    
    def check_session_permission(self, session_token: str, permission: Permission,
                               resource: Optional[str] = None,
                               context: Optional[Dict[str, Any]] = None,
                               raise_on_failure: bool = False) -> bool:
        """
        Check permission using session token.
        
        Args:
            session_token: Session token to validate.
            permission: Permission to check.
            resource: Optional resource being accessed.
            context: Optional context for the permission check.
            raise_on_failure: Whether to raise exception on failure.
            
        Returns:
            True if session user has permission, False otherwise.
            
        Raises:
            AuthorizationError: If raise_on_failure is True and check fails.
        """
        # Validate session
        session = self.session_manager.validate_session(session_token)
        if not session:
            if raise_on_failure:
                raise AuthorizationError("Invalid or expired session", permission)
            return False
        
        # Get user
        user = self._get_user_by_id(session.user_id)
        if not user:
            if raise_on_failure:
                raise AuthorizationError("User not found", permission, session.user_id)
            return False
        
        return self.check_permission(user, permission, resource, context, raise_on_failure)
    
    def check_role_permission(self, role: Role, permission: Permission) -> bool:
        """
        Check if a role has the specified permission.
        
        Args:
            role: Role to check.
            permission: Permission to check.
            
        Returns:
            True if role has permission, False otherwise.
        """
        role_permissions = ROLE_PERMISSIONS.get(role, set())
        return permission in role_permissions
    
    def get_user_permissions(self, user: User) -> Set[Permission]:
        """
        Get all permissions for a user.
        
        Args:
            user: User to get permissions for.
            
        Returns:
            Set of permissions granted to the user.
        """
        return user.get_all_permissions()
    
    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """
        Get all permissions for a role.
        
        Args:
            role: Role to get permissions for.
            
        Returns:
            Set of permissions granted to the role.
        """
        return ROLE_PERMISSIONS.get(role, set())
    
    def validate_role_hierarchy(self, user: User, required_role: Role) -> bool:
        """
        Validate if user has the required role or higher.
        
        Args:
            user: User to validate.
            required_role: Minimum required role.
            
        Returns:
            True if user has required role or higher, False otherwise.
        """
        # Define role hierarchy (higher index = more privileged)
        role_hierarchy = [Role.VIEWER, Role.AUDITOR, Role.OPERATOR, Role.ADMIN]
        
        if required_role not in role_hierarchy:
            return False
        
        required_level = role_hierarchy.index(required_role)
        
        for user_role in user.roles:
            if user_role in role_hierarchy:
                user_level = role_hierarchy.index(user_role)
                if user_level >= required_level:
                    return True
        
        return False
    
    def has_any_permission(self, user: User, permissions: List[Permission]) -> bool:
        """
        Check if user has any of the specified permissions.
        
        Args:
            user: User to check.
            permissions: List of permissions to check for.
            
        Returns:
            True if user has at least one permission, False otherwise.
        """
        user_permissions = self.get_user_permissions(user)
        return any(perm in user_permissions for perm in permissions)
    
    def has_all_permissions(self, user: User, permissions: List[Permission]) -> bool:
        """
        Check if user has all of the specified permissions.
        
        Args:
            user: User to check.
            permissions: List of permissions that must all be present.
            
        Returns:
            True if user has all permissions, False otherwise.
        """
        user_permissions = self.get_user_permissions(user)
        return all(perm in user_permissions for perm in permissions)
    
    @contextmanager
    def authorization_context(self, user: User, operation: str):
        """
        Context manager for tracking authorization operations.
        
        Args:
            user: User performing the operation.
            operation: Description of the operation.
            
        Yields:
            Permission checker instance.
        """
        start_time = logger.info(f"Authorization context started: {operation} for user {user.username}")
        
        try:
            yield self
            logger.info(f"Authorization context completed: {operation}")
        except AuthorizationError as e:
            logger.warning(f"Authorization failed in context {operation}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in authorization context {operation}: {e}")
            raise
        finally:
            logger.debug(f"Authorization context ended: {operation}")
    
    def _apply_context_rules(self, user: User, permission: Permission, 
                           context: Dict[str, Any]) -> bool:
        """
        Apply context-specific authorization rules.
        
        Args:
            user: User being authorized.
            permission: Permission being checked.
            context: Context data for authorization.
            
        Returns:
            True if context rules allow access, False otherwise.
        """
        # Resource ownership rules
        if "owner_id" in context and context["owner_id"] == user.id:
            # Users can always access their own resources
            return True
        
        # Time-based restrictions
        if "require_business_hours" in context and context["require_business_hours"]:
            from datetime import datetime
            now = datetime.now()
            if now.weekday() >= 5 or now.hour < 9 or now.hour >= 17:
                return False
        
        # IP-based restrictions
        if "allowed_ips" in context:
            user_ip = context.get("user_ip")
            if user_ip and user_ip not in context["allowed_ips"]:
                return False
        
        # Custom permission rules
        if "custom_validator" in context:
            validator = context["custom_validator"]
            if callable(validator):
                return validator(user, permission, context)
        
        return True
    
    def _get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID from security manager."""
        return self.security_manager._users_cache.get(user_id)
    
    def _log_permission_event(self, user: User, permission: Permission, 
                            granted: bool, resource: Optional[str] = None,
                            error_message: Optional[str] = None) -> None:
        """Log permission check audit event."""
        event_type = AuthEventType.PERMISSION_GRANTED if granted else AuthEventType.PERMISSION_DENIED
        
        event = AuthEvent(
            event_type=event_type,
            user_id=user.id,
            username=user.username,
            ip_address="127.0.0.1",  # Default IP for internal checks
            resource=resource,
            permission=permission,
            success=granted,
            error_message=error_message,
            metadata={
                "permission_check": True,
                "user_roles": [role.value for role in user.roles]
            }
        )
        
        self.security_manager._log_audit_event(event)


# Decorators for permission checking
def require_permission(permission: Permission, resource_param: Optional[str] = None):
    """
    Decorator to require specific permission for function access.
    
    Args:
        permission: Required permission.
        resource_param: Optional parameter name containing resource identifier.
    
    Returns:
        Decorated function that checks permissions.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get user from function parameters or current session
            user = None
            session_token = None
            
            # Look for user or session_token in kwargs
            if "user" in kwargs:
                user = kwargs["user"]
            elif "session_token" in kwargs:
                session_token = kwargs["session_token"]
            elif len(args) > 0 and isinstance(args[0], User):
                user = args[0]
            
            permission_checker = PermissionChecker()
            
            # Get resource if specified
            resource = None
            if resource_param and resource_param in kwargs:
                resource = str(kwargs[resource_param])
            
            # Check permission
            if user:
                permission_checker.check_permission(user, permission, resource, raise_on_failure=True)
            elif session_token:
                permission_checker.check_session_permission(session_token, permission, resource, raise_on_failure=True)
            else:
                raise AuthorizationError("No user or session provided", permission)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(role: Role):
    """
    Decorator to require specific role for function access.
    
    Args:
        role: Required role.
    
    Returns:
        Decorated function that checks role.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get user from function parameters
            user = None
            if "user" in kwargs:
                user = kwargs["user"]
            elif len(args) > 0 and isinstance(args[0], User):
                user = args[0]
            
            if not user:
                raise AuthorizationError(f"No user provided for role check", None)
            
            permission_checker = PermissionChecker()
            
            if not permission_checker.validate_role_hierarchy(user, role):
                raise AuthorizationError(f"User {user.username} does not have required role {role.value}", None, user.id)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_role(*roles: Role):
    """
    Decorator to require any of the specified roles for function access.
    
    Args:
        *roles: Required roles (user must have at least one).
    
    Returns:
        Decorated function that checks roles.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = None
            if "user" in kwargs:
                user = kwargs["user"]
            elif len(args) > 0 and isinstance(args[0], User):
                user = args[0]
            
            if not user:
                raise AuthorizationError("No user provided for role check", None)
            
            if not any(role in user.roles for role in roles):
                role_names = [role.value for role in roles]
                raise AuthorizationError(
                    f"User {user.username} does not have any of required roles: {role_names}",
                    None, user.id
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global permission checker instance
_permission_checker: Optional[PermissionChecker] = None


def get_permission_checker() -> PermissionChecker:
    """Get the global permission checker instance."""
    global _permission_checker
    if _permission_checker is None:
        _permission_checker = PermissionChecker()
    return _permission_checker