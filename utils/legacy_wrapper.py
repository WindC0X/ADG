"""
Legacy compatibility wrapper for seamless security system transition.

This module provides backward compatibility with existing single-user workflows
while gradually introducing security features through feature flags and
shadow-write validation.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable, Union
from functools import wraps
from contextlib import contextmanager

from .rbac_models import User, Role, Permission, AuthEvent, AuthEventType
from .feature_manager import get_feature_manager
from .security_manager import get_security_manager
from .session_manager import get_session_manager
from .permission_checker import get_permission_checker
from .audit_system import get_audit_logger

logger = logging.getLogger(__name__)


class LegacyUser:
    """Legacy user representation for backward compatibility."""
    def __init__(self, username: str = "legacy_user", user_id: str = "legacy_001"):
        self.username = username
        self.user_id = user_id
        self.email = f"{username}@legacy.local"
        self.roles = {Role.ADMIN}  # Legacy users get admin privileges
        self.is_active = True
        self.is_authenticated = True


class LegacyCompatibilityWrapper:
    """
    Provides backward compatibility for legacy authentication patterns.
    
    Wraps new security functionality with legacy interfaces and provides
    gradual migration capabilities using feature flags.
    """
    
    def __init__(self):
        """Initialize legacy compatibility wrapper."""
        self.feature_manager = get_feature_manager()
        self.security_manager = get_security_manager()
        self.session_manager = get_session_manager()
        self.permission_checker = get_permission_checker()
        self.audit_logger = get_audit_logger()
        
        # Create default legacy user
        self.legacy_user = self._create_legacy_user()
        
        # Initialize security feature flags
        self._init_security_flags()
        
        logger.info("LegacyCompatibilityWrapper initialized")
    
    def _init_security_flags(self) -> None:
        """Initialize security feature flags."""
        security_flags = [
            ("security_authentication", "Enable new authentication system"),
            ("security_authorization", "Enable permission-based authorization"),
            ("security_session_management", "Enable secure session management"),
            ("security_audit_logging", "Enable enhanced audit logging"),
            ("security_rate_limiting", "Enable API rate limiting"),
            ("security_jwt_tokens", "Enable JWT token authentication"),
        ]
        
        for flag_name, description in security_flags:
            try:
                # Only create if doesn't exist
                if not self.feature_manager.is_enabled(flag_name):
                    self.feature_manager.create_flag(
                        name=flag_name,
                        description=description,
                        status=self.feature_manager.FeatureFlagStatus.SHADOW,  # Start in shadow mode
                        rollout_percentage=0.0,
                        expires_in_days=90
                    )
            except ValueError:
                # Flag already exists
                pass
    
    def _create_legacy_user(self) -> User:
        """Create or get legacy user for backward compatibility."""
        try:
            # Try to find existing legacy user
            legacy_user = self.security_manager._get_user_by_username("legacy_user")
            if legacy_user:
                return legacy_user
            
            # Create new legacy user
            return self.security_manager.create_user(
                username="legacy_user",
                email="legacy@adg.local",
                password="legacy_password_placeholder",  # Will be updated
                roles={Role.ADMIN},
                metadata={
                    "legacy_mode": True,
                    "created_by": "compatibility_wrapper",
                    "description": "Default user for legacy compatibility"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create legacy user: {e}")
            # Return a minimal user object
            return User(
                username="legacy_user",
                email="legacy@adg.local",
                password_hash="placeholder",
                salt="placeholder",
                roles={Role.ADMIN}
            )
    
    def authenticate_legacy_request(self, context: Optional[Dict[str, Any]] = None) -> User:
        """
        Authenticate a legacy request with backward compatibility.
        
        Args:
            context: Optional context for authentication (IP, user agent, etc.).
            
        Returns:
            Authenticated user (legacy user if security disabled).
        """
        context = context or {}
        ip_address = context.get('ip_address', '127.0.0.1')
        user_agent = context.get('user_agent', 'Legacy Client')
        
        # Check if new authentication is enabled
        if self.feature_manager.is_enabled('security_authentication'):
            # Try new authentication flow
            auth_header = context.get('authorization')
            session_cookie = context.get('session_cookie')
            
            if auth_header or session_cookie:
                # Use new authentication
                from .core.security_middleware import get_api_security_middleware
                middleware = get_api_security_middleware()
                
                try:
                    headers = {}
                    if auth_header:
                        headers['Authorization'] = auth_header
                    if session_cookie:
                        headers['Cookie'] = f'session={session_cookie}'
                    
                    user = middleware.authenticate_request(
                        auth_header, session_cookie, ip_address, user_agent
                    )
                    if user:
                        return user
                except Exception as e:
                    logger.debug(f"New authentication failed, falling back to legacy: {e}")
        
        # Use legacy authentication (always succeeds)
        self._log_legacy_authentication(ip_address, user_agent)
        return self.legacy_user
    
    def check_legacy_permission(self, user: User, operation: str, 
                               resource: Optional[str] = None,
                               context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check permissions with legacy fallback.
        
        Args:
            user: User to check permissions for.
            operation: Operation being performed.
            resource: Resource being accessed.
            context: Additional context.
            
        Returns:
            True if permission granted (always True in legacy mode).
        """
        # Check if authorization is enabled
        if self.feature_manager.is_enabled('security_authorization'):
            # Map legacy operations to new permissions
            permission = self._map_legacy_operation(operation)
            if permission:
                try:
                    return self.permission_checker.check_permission(
                        user, permission, resource, context
                    )
                except Exception as e:
                    logger.debug(f"Permission check failed, falling back to legacy: {e}")
        
        # Legacy mode - always allow (with logging)
        self._log_legacy_authorization(user, operation, resource, granted=True)
        return True
    
    def create_legacy_session(self, user: User, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Create session with legacy compatibility.
        
        Args:
            user: User to create session for.
            context: Session context (IP address, user agent).
            
        Returns:
            Session token or legacy session identifier.
        """
        context = context or {}
        ip_address = context.get('ip_address', '127.0.0.1')
        user_agent = context.get('user_agent', 'Legacy Client')
        
        # Check if session management is enabled
        if self.feature_manager.is_enabled('security_session_management'):
            try:
                session = self.session_manager.create_session(
                    user, ip_address, user_agent, context
                )
                return session.session_token
            except Exception as e:
                logger.debug(f"Session creation failed, using legacy: {e}")
        
        # Legacy session (simple identifier)
        legacy_token = f"legacy_session_{int(time.time())}"
        self._log_legacy_session_creation(user, legacy_token, ip_address)
        return legacy_token
    
    @contextmanager
    def legacy_context(self, operation: str, user: Optional[User] = None,
                      **kwargs):
        """
        Context manager for legacy operations with new system integration.
        
        Args:
            operation: Operation being performed.
            user: User performing operation (defaults to legacy user).
            **kwargs: Additional context.
        """
        user = user or self.legacy_user
        start_time = time.time()
        
        # Pre-operation setup
        self._log_operation_start(user, operation, kwargs)
        
        try:
            # Check permissions (with legacy fallback)
            if not self.check_legacy_permission(user, operation, kwargs.get('resource'), kwargs):
                raise PermissionError(f"Access denied for operation: {operation}")
            
            yield user
            
            # Post-operation success
            duration = time.time() - start_time
            self._log_operation_success(user, operation, duration, kwargs)
            
        except Exception as e:
            # Post-operation failure
            duration = time.time() - start_time
            self._log_operation_failure(user, operation, str(e), duration, kwargs)
            raise
    
    def wrap_legacy_function(self, operation: str, permission: Optional[Permission] = None):
        """
        Decorator to wrap legacy functions with new security features.
        
        Args:
            operation: Operation name for logging.
            permission: Required permission (if authorization enabled).
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Extract or create user context
                user = kwargs.get('user', self.legacy_user)
                context = kwargs.get('context', {})
                
                # Shadow-write validation if enabled
                if self.feature_manager.should_use_shadow_mode('security_authorization'):
                    return self._shadow_validate_operation(func, user, operation, permission, *args, **kwargs)
                
                # Use legacy context
                with self.legacy_context(operation, user, **context):
                    return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def migrate_to_security(self, user_data: Dict[str, Any]) -> User:
        """
        Migrate legacy user data to new security system.
        
        Args:
            user_data: Legacy user data to migrate.
            
        Returns:
            Migrated user object.
        """
        try:
            # Create new user with proper security
            user = self.security_manager.create_user(
                username=user_data.get('username', 'migrated_user'),
                email=user_data.get('email', 'migrated@adg.local'),
                password=user_data.get('password', 'temporary_password'),
                roles=set(user_data.get('roles', [Role.OPERATOR]))
            )
            
            # Log migration
            self.audit_logger.log_security_event(AuthEvent(
                event_type=AuthEventType.LOGIN_SUCCESS,
                user_id=user.id,
                username=user.username,
                ip_address="127.0.0.1",
                success=True,
                metadata={
                    'migration': True,
                    'legacy_data': user_data,
                    'migration_timestamp': time.time()
                }
            ))
            
            logger.info(f"Migrated legacy user {user_data.get('username')} to security system")
            return user
            
        except Exception as e:
            logger.error(f"Failed to migrate user data: {e}")
            return self.legacy_user
    
    def _map_legacy_operation(self, operation: str) -> Optional[Permission]:
        """Map legacy operation names to new permissions."""
        operation_mapping = {
            'create_directory': Permission.DIRECTORY_CREATE,
            'read_directory': Permission.DIRECTORY_READ,
            'update_directory': Permission.DIRECTORY_UPDATE,
            'delete_directory': Permission.DIRECTORY_DELETE,
            'generate_directory': Permission.DIRECTORY_GENERATE,
            'create_workflow': Permission.WORKFLOW_CREATE,
            'execute_workflow': Permission.WORKFLOW_EXECUTE,
            'manage_users': Permission.USER_MANAGE,
            'system_config': Permission.SYSTEM_CONFIG,
            'read_audit': Permission.AUDIT_READ,
            'upload_file': Permission.FILE_UPLOAD,
            'download_file': Permission.FILE_DOWNLOAD,
            'ai_generate': Permission.AI_GENERATE_CONTENT,
        }
        
        return operation_mapping.get(operation)
    
    def _shadow_validate_operation(self, func: Callable, user: User, operation: str,
                                  permission: Optional[Permission], *args, **kwargs):
        """Perform shadow-write validation of security operation."""
        import time
        
        # Execute legacy function
        legacy_start = time.perf_counter()
        try:
            legacy_result = func(*args, **kwargs)
            legacy_success = True
            legacy_error = None
        except Exception as e:
            legacy_result = None
            legacy_success = False
            legacy_error = str(e)
        legacy_time = (time.perf_counter() - legacy_start) * 1000
        
        # Execute with new security (if enabled)
        new_start = time.perf_counter()
        try:
            if permission:
                # Check permission first
                has_permission = self.permission_checker.check_permission(user, permission)
                if not has_permission:
                    raise PermissionError(f"Access denied: missing {permission.value}")
            
            # Execute function with security context
            new_result = func(*args, **kwargs)
            new_success = True
            new_error = None
        except Exception as e:
            new_result = None
            new_success = False
            new_error = str(e)
        new_time = (time.perf_counter() - new_start) * 1000
        
        # Log shadow validation results
        self._log_shadow_validation(operation, legacy_success, new_success,
                                   legacy_time, new_time, legacy_error, new_error)
        
        # Return appropriate result based on validation mode
        flag = self.feature_manager._flags.get('security_authorization')
        if flag and flag.validation_mode == self.feature_manager.ValidationMode.STRICT:
            if legacy_success != new_success:
                logger.warning(f"Shadow validation mismatch for {operation}: legacy={legacy_success}, new={new_success}")
                # In strict mode, prefer legacy result for safety
                if legacy_error and not new_error:
                    raise Exception(new_error)
                return legacy_result
        
        # Return new result if successful, fallback to legacy
        if new_success:
            return new_result
        elif legacy_success:
            return legacy_result
        else:
            # Both failed - raise the more informative error
            raise Exception(new_error or legacy_error or "Both legacy and new operations failed")
    
    def _log_legacy_authentication(self, ip_address: str, user_agent: str) -> None:
        """Log legacy authentication event."""
        self.audit_logger.log_security_event(AuthEvent(
            event_type=AuthEventType.LOGIN_SUCCESS,
            user_id=self.legacy_user.id,
            username=self.legacy_user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            metadata={'legacy_mode': True, 'authentication_type': 'legacy_bypass'}
        ))
    
    def _log_legacy_authorization(self, user: User, operation: str, 
                                resource: Optional[str], granted: bool) -> None:
        """Log legacy authorization event."""
        self.audit_logger.log_security_event(AuthEvent(
            event_type=AuthEventType.PERMISSION_GRANTED if granted else AuthEventType.PERMISSION_DENIED,
            user_id=user.id,
            username=user.username,
            ip_address="127.0.0.1",
            resource=resource,
            success=granted,
            metadata={'legacy_mode': True, 'operation': operation}
        ))
    
    def _log_legacy_session_creation(self, user: User, token: str, ip_address: str) -> None:
        """Log legacy session creation."""
        self.audit_logger.log_security_event(AuthEvent(
            event_type=AuthEventType.LOGIN_SUCCESS,
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
            success=True,
            metadata={
                'legacy_mode': True,
                'session_type': 'legacy',
                'session_token_prefix': token[:16]
            }
        ))
    
    def _log_operation_start(self, user: User, operation: str, context: Dict[str, Any]) -> None:
        """Log operation start."""
        if self.feature_manager.is_enabled('security_audit_logging'):
            self.audit_logger.log_security_event(AuthEvent(
                event_type=AuthEventType.LOGIN_SUCCESS,  # Generic success event
                user_id=user.id,
                username=user.username,
                ip_address=context.get('ip_address', '127.0.0.1'),
                resource=context.get('resource'),
                success=True,
                metadata={
                    'operation_lifecycle': 'start',
                    'operation': operation,
                    'context': context
                }
            ))
    
    def _log_operation_success(self, user: User, operation: str, duration: float,
                             context: Dict[str, Any]) -> None:
        """Log operation success."""
        if self.feature_manager.is_enabled('security_audit_logging'):
            self.audit_logger.log_security_event(AuthEvent(
                event_type=AuthEventType.PERMISSION_GRANTED,
                user_id=user.id,
                username=user.username,
                ip_address=context.get('ip_address', '127.0.0.1'),
                resource=context.get('resource'),
                success=True,
                metadata={
                    'operation_lifecycle': 'success',
                    'operation': operation,
                    'duration_ms': duration * 1000,
                    'context': context
                }
            ))
    
    def _log_operation_failure(self, user: User, operation: str, error: str,
                             duration: float, context: Dict[str, Any]) -> None:
        """Log operation failure."""
        if self.feature_manager.is_enabled('security_audit_logging'):
            self.audit_logger.log_security_event(AuthEvent(
                event_type=AuthEventType.PERMISSION_DENIED,
                user_id=user.id,
                username=user.username,
                ip_address=context.get('ip_address', '127.0.0.1'),
                resource=context.get('resource'),
                success=False,
                error_message=error,
                metadata={
                    'operation_lifecycle': 'failure',
                    'operation': operation,
                    'duration_ms': duration * 1000,
                    'context': context
                }
            ))
    
    def _log_shadow_validation(self, operation: str, legacy_success: bool, new_success: bool,
                             legacy_time: float, new_time: float,
                             legacy_error: Optional[str], new_error: Optional[str]) -> None:
        """Log shadow validation results."""
        self.audit_logger.log_security_event(AuthEvent(
            event_type=AuthEventType.LOGIN_SUCCESS,
            user_id=self.legacy_user.id,
            username=self.legacy_user.username,
            ip_address="127.0.0.1",
            success=True,
            metadata={
                'shadow_validation': True,
                'operation': operation,
                'legacy_success': legacy_success,
                'new_success': new_success,
                'legacy_time_ms': legacy_time,
                'new_time_ms': new_time,
                'legacy_error': legacy_error,
                'new_error': new_error,
                'validation_match': legacy_success == new_success
            }
        ))


# Convenience functions for legacy integration
def authenticate_legacy_user(context: Optional[Dict[str, Any]] = None) -> User:
    """Convenience function to authenticate legacy user."""
    wrapper = get_legacy_wrapper()
    return wrapper.authenticate_legacy_request(context)


def check_legacy_access(operation: str, user: Optional[User] = None,
                       resource: Optional[str] = None) -> bool:
    """Convenience function to check legacy access."""
    wrapper = get_legacy_wrapper()
    user = user or wrapper.legacy_user
    return wrapper.check_legacy_permission(user, operation, resource)


def legacy_operation(operation: str, permission: Optional[Permission] = None):
    """Decorator for legacy operations."""
    wrapper = get_legacy_wrapper()
    return wrapper.wrap_legacy_function(operation, permission)


# Global wrapper instance
_legacy_wrapper: Optional[LegacyCompatibilityWrapper] = None


def get_legacy_wrapper() -> LegacyCompatibilityWrapper:
    """Get global legacy compatibility wrapper instance."""
    global _legacy_wrapper
    if _legacy_wrapper is None:
        _legacy_wrapper = LegacyCompatibilityWrapper()
    return _legacy_wrapper