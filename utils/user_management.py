"""
User management interfaces and CRUD operations for the ADG security system.

This module provides comprehensive user management functionality including
user creation, updates, role management, password changes, and account
lifecycle operations with proper audit logging and security controls.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import asdict

from .rbac_models import User, Role, Permission, AuthEvent, AuthEventType, ValidationResult
from core.node_interfaces import ValidationSeverity
from .security_manager import get_security_manager
from .permission_checker import get_permission_checker, require_permission, AuthorizationError
from .audit_system import get_audit_logger

logger = logging.getLogger(__name__)


class UserNotFoundError(Exception):
    """Raised when a user is not found."""
    pass


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists."""
    pass


class UserManagementService:
    """
    Comprehensive user management service with CRUD operations.
    
    Provides secure user lifecycle management including creation, updates,
    role management, password changes, and account operations with proper
    audit logging and permission checking.
    """
    
    def __init__(self):
        """Initialize user management service."""
        self.security_manager = get_security_manager()
        self.permission_checker = get_permission_checker()
        self.audit_logger = get_audit_logger()
        
        logger.info("UserManagementService initialized")
    
    @require_permission(Permission.USER_MANAGE)
    def create_user(self, admin_user: User, username: str, email: str, password: str,
                   roles: Set[Role], **kwargs) -> User:
        """
        Create a new user with specified roles.
        
        Args:
            admin_user: Administrator creating the user.
            username: Unique username for the new user.
            email: Email address for the new user.
            password: Initial password.
            roles: Set of roles to assign.
            **kwargs: Additional user properties.
            
        Returns:
            Created user object.
            
        Raises:
            UserAlreadyExistsError: If user already exists.
            AuthorizationError: If admin lacks permission.
            ValueError: If validation fails.
        """
        try:
            # Check if user already exists
            existing_user = self.security_manager._get_user_by_username(username)
            if existing_user:
                raise UserAlreadyExistsError(f"User '{username}' already exists")
            
            # Validate role assignment permissions
            self._validate_role_assignment(admin_user, roles)
            
            # Create user through security manager
            user = self.security_manager.create_user(
                username=username,
                email=email,
                password=password,
                roles=roles,
                **kwargs
            )
            
            # Log user creation
            self._log_user_event(admin_user, "user_created", user.id, {
                'created_username': username,
                'assigned_roles': [r.value for r in roles]
            })
            
            logger.info(f"User '{username}' created by admin '{admin_user.username}'")
            return user
            
        except Exception as e:
            # Log failed creation attempt
            self._log_user_event(admin_user, "user_creation_failed", None, {
                'attempted_username': username,
                'error': str(e)
            })
            raise
    
    @require_permission(Permission.USER_MANAGE)
    def get_user(self, admin_user: User, user_id: str) -> User:
        """
        Retrieve user by ID.
        
        Args:
            admin_user: Administrator requesting user info.
            user_id: User ID to retrieve.
            
        Returns:
            User object.
            
        Raises:
            UserNotFoundError: If user is not found.
            AuthorizationError: If admin lacks permission.
        """
        user = self.security_manager._users_cache.get(user_id)
        if not user:
            # Try loading from database
            with self.security_manager._lock:
                # This is a simplified lookup - in real implementation,
                # we'd need a proper database query method
                for cached_user in self.security_manager._users_cache.values():
                    if cached_user.id == user_id:
                        user = cached_user
                        break
        
        if not user:
            raise UserNotFoundError(f"User with ID '{user_id}' not found")
        
        # Log user access
        self._log_user_event(admin_user, "user_accessed", user_id, {
            'accessed_username': user.username
        })
        
        return user
    
    @require_permission(Permission.USER_MANAGE)
    def list_users(self, admin_user: User, active_only: bool = True,
                  limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List users with pagination and filtering.
        
        Args:
            admin_user: Administrator requesting user list.
            active_only: Whether to return only active users.
            limit: Maximum number of users to return.
            offset: Number of users to skip.
            
        Returns:
            List of user dictionaries (without sensitive data).
        """
        users = []
        all_users = list(self.security_manager._users_cache.values())
        
        # Filter active users if requested
        if active_only:
            all_users = [u for u in all_users if u.is_active]
        
        # Apply pagination
        paginated_users = all_users[offset:offset + limit]
        
        # Convert to safe dictionaries (exclude sensitive data)
        for user in paginated_users:
            user_dict = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'roles': [r.value for r in user.roles],
                'is_active': user.is_active,
                'is_locked': user.is_locked,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'failed_login_attempts': user.failed_login_attempts,
                'is_password_expired': user.is_password_expired()
            }
            users.append(user_dict)
        
        # Log user list access
        self._log_user_event(admin_user, "user_list_accessed", None, {
            'users_returned': len(users),
            'active_only': active_only,
            'limit': limit,
            'offset': offset
        })
        
        return users
    
    @require_permission(Permission.USER_MANAGE)
    def update_user(self, admin_user: User, user_id: str, **updates) -> User:
        """
        Update user properties.
        
        Args:
            admin_user: Administrator updating the user.
            user_id: ID of user to update.
            **updates: Properties to update.
            
        Returns:
            Updated user object.
            
        Raises:
            UserNotFoundError: If user is not found.
            AuthorizationError: If admin lacks permission.
        """
        user = self.get_user(admin_user, user_id)
        
        # Track changes for audit
        changes = {}
        
        # Update allowed properties
        allowed_updates = ['email', 'is_active', 'metadata']
        for field, value in updates.items():
            if field in allowed_updates:
                old_value = getattr(user, field)
                if old_value != value:
                    setattr(user, field, value)
                    changes[field] = {'old': old_value, 'new': value}
        
        # Update timestamp
        user.updated_at = datetime.utcnow()
        
        # Save changes
        self.security_manager._save_user_to_db(user)
        self.security_manager._users_cache[user.id] = user
        
        # Log user update
        self._log_user_event(admin_user, "user_updated", user_id, {
            'updated_username': user.username,
            'changes': changes
        })
        
        logger.info(f"User '{user.username}' updated by admin '{admin_user.username}': {list(changes.keys())}")
        return user
    
    @require_permission(Permission.ROLE_MANAGE)
    def assign_role(self, admin_user: User, user_id: str, role: Role) -> User:
        """
        Assign a role to a user.
        
        Args:
            admin_user: Administrator assigning the role.
            user_id: ID of user to assign role to.
            role: Role to assign.
            
        Returns:
            Updated user object.
        """
        user = self.get_user(admin_user, user_id)
        
        # Validate role assignment
        self._validate_role_assignment(admin_user, {role})
        
        if role not in user.roles:
            user.add_role(role)
            
            # Save changes
            self.security_manager._save_user_to_db(user)
            self.security_manager._users_cache[user.id] = user
            
            # Log role assignment
            self._log_user_event(admin_user, "role_assigned", user_id, {
                'username': user.username,
                'assigned_role': role.value
            })
            
            logger.info(f"Role '{role.value}' assigned to user '{user.username}' by admin '{admin_user.username}'")
        
        return user
    
    @require_permission(Permission.ROLE_MANAGE)
    def revoke_role(self, admin_user: User, user_id: str, role: Role) -> User:
        """
        Revoke a role from a user.
        
        Args:
            admin_user: Administrator revoking the role.
            user_id: ID of user to revoke role from.
            role: Role to revoke.
            
        Returns:
            Updated user object.
        """
        user = self.get_user(admin_user, user_id)
        
        if role in user.roles:
            # Ensure user retains at least one role
            if len(user.roles) == 1:
                raise ValueError("Cannot revoke last role from user")
            
            user.remove_role(role)
            
            # Save changes
            self.security_manager._save_user_to_db(user)
            self.security_manager._users_cache[user.id] = user
            
            # Log role revocation
            self._log_user_event(admin_user, "role_revoked", user_id, {
                'username': user.username,
                'revoked_role': role.value
            })
            
            logger.info(f"Role '{role.value}' revoked from user '{user.username}' by admin '{admin_user.username}'")
        
        return user
    
    def change_password(self, user: User, old_password: str, new_password: str) -> None:
        """
        Change user's password (self-service).
        
        Args:
            user: User changing their password.
            old_password: Current password for verification.
            new_password: New password.
            
        Raises:
            ValueError: If old password is incorrect or new password is invalid.
        """
        # Verify old password
        if not self.security_manager.password_hasher.verify_password(
            old_password, user.salt, user.password_hash
        ):
            # Log failed password change attempt
            self._log_user_event(user, "password_change_failed", user.id, {
                'reason': 'incorrect_old_password'
            })
            raise ValueError("Current password is incorrect")
        
        # Validate new password strength
        password_validation = self.security_manager.password_hasher.validate_password_strength(
            new_password, self.security_manager.config
        )
        
        validation_errors = [r for r in password_validation if not r.is_valid]
        if validation_errors:
            error_messages = [r.message for r in validation_errors]
            raise ValueError(f"New password validation failed: {'; '.join(error_messages)}")
        
        # Update password
        user.salt = self.security_manager.password_hasher.generate_salt()
        user.password_hash = self.security_manager.password_hasher.hash_password(new_password, user.salt)
        user.last_password_change = datetime.utcnow()
        user.password_expires_at = datetime.utcnow() + timedelta(days=self.security_manager.config.password_expiry_days)
        user.updated_at = datetime.utcnow()
        
        # Save changes
        self.security_manager._save_user_to_db(user)
        self.security_manager._users_cache[user.id] = user
        
        # Log successful password change
        self._log_user_event(user, "password_changed", user.id, {
            'self_service': True
        })
        
        logger.info(f"Password changed for user '{user.username}'")
    
    @require_permission(Permission.USER_MANAGE)
    def reset_password(self, admin_user: User, user_id: str, new_password: str,
                      force_change_on_login: bool = True) -> None:
        """
        Reset user's password (admin operation).
        
        Args:
            admin_user: Administrator resetting the password.
            user_id: ID of user whose password to reset.
            new_password: New password.
            force_change_on_login: Whether to force password change on next login.
        """
        user = self.get_user(admin_user, user_id)
        
        # Validate new password strength
        password_validation = self.security_manager.password_hasher.validate_password_strength(
            new_password, self.security_manager.config
        )
        
        validation_errors = [r for r in password_validation if not r.is_valid]
        if validation_errors:
            error_messages = [r.message for r in validation_errors]
            raise ValueError(f"Password validation failed: {'; '.join(error_messages)}")
        
        # Update password
        user.salt = self.security_manager.password_hasher.generate_salt()
        user.password_hash = self.security_manager.password_hasher.hash_password(new_password, user.salt)
        user.last_password_change = datetime.utcnow()
        
        if force_change_on_login:
            # Set password to expire immediately
            user.password_expires_at = datetime.utcnow()
        else:
            user.password_expires_at = datetime.utcnow() + timedelta(days=self.security_manager.config.password_expiry_days)
        
        user.updated_at = datetime.utcnow()
        
        # Reset failed login attempts
        user.reset_failed_attempts()
        
        # Unlock account if locked
        if user.is_locked:
            user.is_locked = False
        
        # Save changes
        self.security_manager._save_user_to_db(user)
        self.security_manager._users_cache[user.id] = user
        
        # Log password reset
        self._log_user_event(admin_user, "password_reset", user_id, {
            'reset_username': user.username,
            'force_change_on_login': force_change_on_login,
            'admin_initiated': True
        })
        
        logger.info(f"Password reset for user '{user.username}' by admin '{admin_user.username}'")
    
    @require_permission(Permission.USER_MANAGE)
    def lock_user(self, admin_user: User, user_id: str, reason: str = "Admin action") -> User:
        """
        Lock a user account.
        
        Args:
            admin_user: Administrator locking the account.
            user_id: ID of user to lock.
            reason: Reason for locking.
            
        Returns:
            Updated user object.
        """
        user = self.get_user(admin_user, user_id)
        
        if not user.is_locked:
            user.is_locked = True
            user.updated_at = datetime.utcnow()
            
            # Save changes
            self.security_manager._save_user_to_db(user)
            self.security_manager._users_cache[user.id] = user
            
            # Revoke active sessions
            from .session_manager import get_session_manager
            session_manager = get_session_manager()
            revoked_sessions = session_manager.revoke_user_sessions(user_id, reason=f"account_locked: {reason}")
            
            # Log account lock
            self._log_user_event(admin_user, "account_locked", user_id, {
                'locked_username': user.username,
                'reason': reason,
                'revoked_sessions': revoked_sessions
            })
            
            logger.info(f"Account locked for user '{user.username}' by admin '{admin_user.username}': {reason}")
        
        return user
    
    @require_permission(Permission.USER_MANAGE)
    def unlock_user(self, admin_user: User, user_id: str, reason: str = "Admin action") -> User:
        """
        Unlock a user account.
        
        Args:
            admin_user: Administrator unlocking the account.
            user_id: ID of user to unlock.
            reason: Reason for unlocking.
            
        Returns:
            Updated user object.
        """
        user = self.get_user(admin_user, user_id)
        
        if user.is_locked:
            user.is_locked = False
            user.reset_failed_attempts()
            user.updated_at = datetime.utcnow()
            
            # Save changes
            self.security_manager._save_user_to_db(user)
            self.security_manager._users_cache[user.id] = user
            
            # Log account unlock
            self._log_user_event(admin_user, "account_unlocked", user_id, {
                'unlocked_username': user.username,
                'reason': reason
            })
            
            logger.info(f"Account unlocked for user '{user.username}' by admin '{admin_user.username}': {reason}")
        
        return user
    
    @require_permission(Permission.USER_MANAGE)
    def deactivate_user(self, admin_user: User, user_id: str, reason: str = "Admin action") -> User:
        """
        Deactivate a user account.
        
        Args:
            admin_user: Administrator deactivating the account.
            user_id: ID of user to deactivate.
            reason: Reason for deactivation.
            
        Returns:
            Updated user object.
        """
        user = self.get_user(admin_user, user_id)
        
        if user.is_active:
            user.is_active = False
            user.updated_at = datetime.utcnow()
            
            # Save changes
            self.security_manager._save_user_to_db(user)
            self.security_manager._users_cache[user.id] = user
            
            # Revoke active sessions
            from .session_manager import get_session_manager
            session_manager = get_session_manager()
            revoked_sessions = session_manager.revoke_user_sessions(user_id, reason=f"account_deactivated: {reason}")
            
            # Log account deactivation
            self._log_user_event(admin_user, "account_deactivated", user_id, {
                'deactivated_username': user.username,
                'reason': reason,
                'revoked_sessions': revoked_sessions
            })
            
            logger.info(f"Account deactivated for user '{user.username}' by admin '{admin_user.username}': {reason}")
        
        return user
    
    def get_user_permissions(self, user: User) -> Set[Permission]:
        """
        Get all permissions for a user.
        
        Args:
            user: User to get permissions for.
            
        Returns:
            Set of permissions granted to the user.
        """
        return self.permission_checker.get_user_permissions(user)
    
    def validate_user_data(self, user_data: Dict[str, Any]) -> List[ValidationResult]:
        """
        Validate user data before creation or update.
        
        Args:
            user_data: User data to validate.
            
        Returns:
            List of validation results.
        """
        results = []
        
        # Create temporary user for validation
        try:
            temp_user = User(
                username=user_data.get('username', ''),
                email=user_data.get('email', ''),
                password_hash='temp',
                salt='temp',
                roles=set(user_data.get('roles', []))
            )
            
            results.extend(temp_user.validate())
            
        except Exception as e:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"User data validation failed: {str(e)}",
                field_name="user_data",
                error_code="INVALID_USER_DATA"
            ))
        
        return results
    
    def _validate_role_assignment(self, admin_user: User, roles: Set[Role]) -> None:
        """Validate that admin can assign the specified roles."""
        # Only admins can assign admin role
        if Role.ADMIN in roles and Role.ADMIN not in admin_user.roles:
            raise AuthorizationError(
                "Only administrators can assign administrator role",
                Permission.ROLE_MANAGE,
                admin_user.id
            )
        
        # Additional role assignment validations can be added here
    
    def _log_user_event(self, admin_user: User, action: str, target_user_id: Optional[str],
                       metadata: Dict[str, Any]) -> None:
        """Log user management event."""
        event = AuthEvent(
            event_type=AuthEventType.ROLE_ASSIGNED if 'assigned' in action else AuthEventType.LOGIN_SUCCESS,
            user_id=admin_user.id,
            username=admin_user.username,
            ip_address="127.0.0.1",  # Will be updated by caller if available
            success=True,
            metadata={
                'user_management_action': action,
                'target_user_id': target_user_id,
                **metadata
            }
        )
        
        self.audit_logger.log_security_event(event)


# Global user management service instance
_user_management_service: Optional[UserManagementService] = None


def get_user_management_service() -> UserManagementService:
    """Get the global user management service instance."""
    global _user_management_service
    if _user_management_service is None:
        _user_management_service = UserManagementService()
    return _user_management_service