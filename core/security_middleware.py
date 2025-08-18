"""
API security middleware for request authentication and authorization.

This module provides comprehensive API security with JWT authentication,
session validation, rate limiting, permission checking, and standardized
error responses.
"""

import json
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from functools import wraps
from urllib.parse import urlparse

from .rbac_models import User, Permission, Role, AuthEvent, AuthEventType
from .security_manager import get_security_manager
from .session_manager import get_session_manager
from .jwt_manager import get_jwt_manager
from .permission_checker import get_permission_checker, AuthorizationError

logger = logging.getLogger(__name__)


class APISecurityError(Exception):
    """Base exception for API security errors."""
    def __init__(self, message: str, status_code: int = 401, 
                 error_code: str = "SECURITY_ERROR", trace_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.trace_id = trace_id


class RateLimitExceeded(APISecurityError):
    """Exception raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int, trace_id: Optional[str] = None):
        super().__init__(message, 429, "RATE_LIMIT_EXCEEDED", trace_id)
        self.retry_after = retry_after


class AuthenticationRequired(APISecurityError):
    """Exception raised when authentication is required."""
    def __init__(self, message: str = "Authentication required", trace_id: Optional[str] = None):
        super().__init__(message, 401, "AUTHENTICATION_REQUIRED", trace_id)


class InsufficientPermissions(APISecurityError):
    """Exception raised when user lacks required permissions."""
    def __init__(self, message: str, permission: Permission, trace_id: Optional[str] = None):
        super().__init__(message, 403, "INSUFFICIENT_PERMISSIONS", trace_id)
        self.permission = permission


class RateLimiter:
    """
    Rate limiting implementation with role-based limits.
    
    Implements sliding window rate limiting with per-user tracking
    and configurable limits based on user roles.
    """
    
    def __init__(self):
        """Initialize rate limiter."""
        self._requests = defaultdict(list)  # user_id -> [(timestamp, endpoint), ...]
        self._lock = threading.RLock()
        self.security_manager = get_security_manager()
    
    def check_rate_limit(self, user: User, endpoint: str, window_minutes: int = 60) -> Tuple[bool, int]:
        """
        Check if user is within rate limits.
        
        Args:
            user: User making the request.
            endpoint: API endpoint being accessed.
            window_minutes: Time window for rate limiting in minutes.
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        with self._lock:
            now = time.time()
            window_start = now - (window_minutes * 60)
            
            # Get rate limit for user's highest role
            rate_limit = self._get_user_rate_limit(user)
            
            # Clean old requests
            user_requests = self._requests[user.id]
            user_requests[:] = [(ts, ep) for ts, ep in user_requests if ts > window_start]
            
            # Check current request count
            current_count = len(user_requests)
            
            if current_count >= rate_limit:
                # Calculate retry after time
                oldest_request = min(user_requests, key=lambda x: x[0])[0] if user_requests else now
                retry_after = int((oldest_request + (window_minutes * 60)) - now)
                return False, max(retry_after, 1)
            
            # Record this request
            user_requests.append((now, endpoint))
            return True, 0
    
    def _get_user_rate_limit(self, user: User) -> int:
        """Get rate limit for user based on their highest privilege role."""
        # Role hierarchy (higher index = higher privilege)
        role_hierarchy = [Role.VIEWER, Role.AUDITOR, Role.OPERATOR, Role.ADMIN]
        
        # Find highest privilege role
        user_roles = user.roles
        max_role = Role.VIEWER  # Default
        
        for role in role_hierarchy:
            if role in user_roles:
                max_role = role
        
        return self.security_manager.config.get_rate_limit_for_role(max_role)


class EndpointPermissionMapper:
    """
    Maps API endpoints to required permissions.
    
    Provides flexible endpoint-to-permission mapping with support for
    HTTP methods, path patterns, and dynamic permission resolution.
    """
    
    def __init__(self):
        """Initialize endpoint permission mapper."""
        self.mappings = self._build_default_mappings()
    
    def get_required_permissions(self, method: str, path: str) -> List[Permission]:
        """
        Get required permissions for an API endpoint.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            path: API endpoint path.
            
        Returns:
            List of required permissions.
        """
        # Normalize method
        method = method.upper()
        
        # Try exact match first
        key = f"{method} {path}"
        if key in self.mappings:
            return self.mappings[key]
        
        # Try pattern matching
        for pattern, permissions in self.mappings.items():
            if self._match_pattern(pattern, f"{method} {path}"):
                return permissions
        
        # Default permissions for unmatched endpoints
        return self._get_default_permissions(method, path)
    
    def add_mapping(self, method: str, path: str, permissions: List[Permission]) -> None:
        """
        Add endpoint permission mapping.
        
        Args:
            method: HTTP method.
            path: API endpoint path.
            permissions: Required permissions.
        """
        key = f"{method.upper()} {path}"
        self.mappings[key] = permissions
    
    def _build_default_mappings(self) -> Dict[str, List[Permission]]:
        """Build default endpoint permission mappings."""
        return {
            # Authentication endpoints (no permissions required)
            "POST /api/v1/auth/login": [],
            "POST /api/v1/auth/logout": [],
            "POST /api/v1/auth/refresh": [],
            "GET /api/v1/auth/jwks": [],
            
            # User management endpoints
            "GET /api/v1/users": [Permission.USER_MANAGE],
            "POST /api/v1/users": [Permission.USER_MANAGE],
            "GET /api/v1/users/*": [Permission.USER_MANAGE],
            "PUT /api/v1/users/*": [Permission.USER_MANAGE],
            "DELETE /api/v1/users/*": [Permission.USER_MANAGE],
            "PUT /api/v1/users/*/roles": [Permission.ROLE_MANAGE],
            
            # Directory operations
            "GET /api/v1/directories": [Permission.DIRECTORY_READ],
            "POST /api/v1/directories": [Permission.DIRECTORY_CREATE],
            "PUT /api/v1/directories/*": [Permission.DIRECTORY_UPDATE],
            "DELETE /api/v1/directories/*": [Permission.DIRECTORY_DELETE],
            "POST /api/v1/directories/*/generate": [Permission.DIRECTORY_GENERATE],
            
            # Workflow management
            "GET /api/v1/workflows": [Permission.WORKFLOW_READ],
            "POST /api/v1/workflows": [Permission.WORKFLOW_CREATE],
            "PUT /api/v1/workflows/*": [Permission.WORKFLOW_UPDATE],
            "DELETE /api/v1/workflows/*": [Permission.WORKFLOW_DELETE],
            "POST /api/v1/workflows/*/execute": [Permission.WORKFLOW_EXECUTE],
            
            # AI features
            "POST /api/v1/ai/generate": [Permission.AI_GENERATE_CONTENT],
            "POST /api/v1/ai/analyze": [Permission.AI_ANALYZE_DATA],
            "POST /api/v1/ai/optimize": [Permission.AI_OPTIMIZE_WORKFLOW],
            
            # File operations
            "POST /api/v1/files/upload": [Permission.FILE_UPLOAD],
            "GET /api/v1/files/*": [Permission.FILE_DOWNLOAD],
            "DELETE /api/v1/files/*": [Permission.FILE_DELETE],
            
            # Template management
            "GET /api/v1/templates": [Permission.TEMPLATE_READ],
            "POST /api/v1/templates": [Permission.TEMPLATE_CREATE],
            "PUT /api/v1/templates/*": [Permission.TEMPLATE_UPDATE],
            "DELETE /api/v1/templates/*": [Permission.TEMPLATE_DELETE],
            
            # System administration
            "GET /api/v1/system/config": [Permission.SYSTEM_CONFIG],
            "PUT /api/v1/system/config": [Permission.SYSTEM_CONFIG],
            "GET /api/v1/system/audit": [Permission.AUDIT_READ],
            "POST /api/v1/system/security": [Permission.SECURITY_MANAGE],
        }
    
    def _match_pattern(self, pattern: str, endpoint: str) -> bool:
        """Match endpoint against pattern with wildcard support."""
        # Simple wildcard matching (* matches any path segment)
        if '*' not in pattern:
            return pattern == endpoint
        
        pattern_parts = pattern.split('/')
        endpoint_parts = endpoint.split('/')
        
        if len(pattern_parts) != len(endpoint_parts):
            return False
        
        for p_part, e_part in zip(pattern_parts, endpoint_parts):
            if p_part != '*' and p_part != e_part:
                return False
        
        return True
    
    def _get_default_permissions(self, method: str, path: str) -> List[Permission]:
        """Get default permissions for unmatched endpoints."""
        # Default permission based on HTTP method
        if method in ['GET', 'HEAD', 'OPTIONS']:
            return [Permission.DIRECTORY_READ]  # Read operations
        elif method in ['POST', 'PUT', 'PATCH']:
            return [Permission.DIRECTORY_UPDATE]  # Write operations
        elif method == 'DELETE':
            return [Permission.DIRECTORY_DELETE]  # Delete operations
        
        return [Permission.DIRECTORY_READ]  # Conservative default


class APISecurityMiddleware:
    """
    Comprehensive API security middleware.
    
    Handles authentication, authorization, rate limiting, and security
    logging for all API requests with support for both JWT tokens
    and session-based authentication.
    """
    
    def __init__(self, enable_rate_limiting: bool = True):
        """
        Initialize API security middleware.
        
        Args:
            enable_rate_limiting: Whether to enable rate limiting.
        """
        self.security_manager = get_security_manager()
        self.session_manager = get_session_manager()
        self.jwt_manager = get_jwt_manager()
        self.permission_checker = get_permission_checker()
        
        self.rate_limiter = RateLimiter() if enable_rate_limiting else None
        self.endpoint_mapper = EndpointPermissionMapper()
        
        # Track failed authentication attempts
        self._failed_attempts = defaultdict(list)  # ip_address -> [timestamp, ...]
        
        logger.info("APISecurityMiddleware initialized")
    
    def authenticate_request(self, authorization_header: Optional[str], 
                           session_cookie: Optional[str],
                           ip_address: str, user_agent: str = "") -> Optional[User]:
        """
        Authenticate API request using JWT token or session.
        
        Args:
            authorization_header: Authorization header value.
            session_cookie: Session cookie value.
            ip_address: Client IP address.
            user_agent: Client user agent.
            
        Returns:
            Authenticated user or None if authentication fails.
        """
        import secrets
        trace_id = secrets.token_hex(8)
        
        # Try JWT authentication first
        if authorization_header:
            user = self._authenticate_jwt(authorization_header, ip_address, user_agent, trace_id)
            if user:
                return user
        
        # Try session authentication
        if session_cookie:
            user = self._authenticate_session(session_cookie, ip_address, user_agent, trace_id)
            if user:
                return user
        
        # Authentication failed
        self._log_failed_attempt(ip_address, user_agent, trace_id)
        return None
    
    def authorize_request(self, user: User, method: str, path: str,
                         resource_id: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Authorize API request based on permissions.
        
        Args:
            user: Authenticated user.
            method: HTTP method.
            path: API endpoint path.
            resource_id: Optional resource identifier.
            context: Optional authorization context.
            
        Returns:
            True if authorized, False otherwise.
        """
        required_permissions = self.endpoint_mapper.get_required_permissions(method, path)
        
        # No permissions required (e.g., public endpoints)
        if not required_permissions:
            return True
        
        # Check each required permission
        for permission in required_permissions:
            if not self.permission_checker.check_permission(
                user, permission, resource_id, context
            ):
                return False
        
        return True
    
    def check_rate_limit(self, user: User, endpoint: str) -> None:
        """
        Check rate limit for user request.
        
        Args:
            user: User making the request.
            endpoint: API endpoint being accessed.
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded.
        """
        if not self.rate_limiter or not self.security_manager.config.enable_rate_limiting:
            return
        
        is_allowed, retry_after = self.rate_limiter.check_rate_limit(user, endpoint)
        
        if not is_allowed:
            import secrets
            trace_id = secrets.token_hex(8)
            
            # Log rate limit violation
            event = AuthEvent(
                event_type=AuthEventType.PERMISSION_DENIED,
                user_id=user.id,
                username=user.username,
                ip_address="127.0.0.1",  # Will be updated by caller
                resource=endpoint,
                success=False,
                error_message="Rate limit exceeded",
                trace_id=trace_id,
                metadata={"rate_limit_exceeded": True, "retry_after": retry_after}
            )
            self.security_manager._log_audit_event(event)
            
            raise RateLimitExceeded(
                f"Rate limit exceeded. Try again in {retry_after} seconds.",
                retry_after, trace_id
            )
    
    def process_request(self, method: str, path: str, headers: Dict[str, str],
                       ip_address: str, user_agent: str = "",
                       resource_id: Optional[str] = None,
                       context: Optional[Dict[str, Any]] = None) -> User:
        """
        Process API request with full security validation.
        
        Args:
            method: HTTP method.
            path: API endpoint path.
            headers: Request headers.
            ip_address: Client IP address.
            user_agent: Client user agent.
            resource_id: Optional resource identifier.
            context: Optional authorization context.
            
        Returns:
            Authenticated and authorized user.
            
        Raises:
            APISecurityError: If security validation fails.
        """
        import secrets
        trace_id = secrets.token_hex(8)
        
        try:
            # Extract authentication data
            authorization_header = headers.get('Authorization')
            session_cookie = headers.get('Cookie', '').split('session=')[1].split(';')[0] if 'session=' in headers.get('Cookie', '') else None
            
            # Authenticate request
            user = self.authenticate_request(
                authorization_header, session_cookie, ip_address, user_agent
            )
            
            if not user:
                raise AuthenticationRequired(trace_id=trace_id)
            
            # Check rate limits
            self.check_rate_limit(user, path)
            
            # Authorize request
            if context:
                context["user_ip"] = ip_address
            
            if not self.authorize_request(user, method, path, resource_id, context):
                required_perms = self.endpoint_mapper.get_required_permissions(method, path)
                perm_names = [p.value for p in required_perms]
                
                raise InsufficientPermissions(
                    f"User {user.username} lacks required permissions: {perm_names}",
                    required_perms[0] if required_perms else Permission.DIRECTORY_READ,
                    trace_id
                )
            
            # Log successful request
            event = AuthEvent(
                event_type=AuthEventType.PERMISSION_GRANTED,
                user_id=user.id,
                username=user.username,
                ip_address=ip_address,
                user_agent=user_agent,
                resource=f"{method} {path}",
                success=True,
                trace_id=trace_id,
                metadata={"endpoint_access": True}
            )
            self.security_manager._log_audit_event(event)
            
            return user
            
        except APISecurityError:
            raise
        except Exception as e:
            logger.error(f"API security processing error: {e}")
            raise APISecurityError(
                "Internal security error", 500, "INTERNAL_ERROR", trace_id
            )
    
    def create_error_response(self, error: APISecurityError) -> Dict[str, Any]:
        """
        Create standardized error response.
        
        Args:
            error: Security error to format.
            
        Returns:
            Standardized error response dictionary.
        """
        response = {
            "error": {
                "code": error.error_code,
                "message": error.message,
                "trace_id": error.trace_id or "unknown"
            }
        }
        
        # Add retry-after header for rate limit errors
        if isinstance(error, RateLimitExceeded):
            response["retry_after"] = error.retry_after
        
        # Add additional context for permission errors
        if isinstance(error, InsufficientPermissions):
            response["error"]["permission"] = error.permission.value
        
        return response
    
    def _authenticate_jwt(self, authorization_header: str, ip_address: str,
                         user_agent: str, trace_id: str) -> Optional[User]:
        """Authenticate using JWT token."""
        try:
            # Extract token from header
            if not authorization_header.startswith('Bearer '):
                return None
            
            token = authorization_header[7:]  # Remove 'Bearer ' prefix
            
            # Validate token
            claims = self.jwt_manager.validate_token(token, 'access')
            if not claims:
                return None
            
            # Get user
            user_id = claims.get('sub')
            user = self.security_manager._users_cache.get(user_id)
            
            if user and user.is_active and not user.is_locked:
                # Log successful JWT authentication
                event = AuthEvent(
                    event_type=AuthEventType.LOGIN_SUCCESS,
                    user_id=user.id,
                    username=user.username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                    trace_id=trace_id,
                    metadata={"auth_method": "jwt", "jti": claims.get('jti')}
                )
                self.security_manager._log_audit_event(event)
                
                return user
            
        except Exception as e:
            logger.warning(f"JWT authentication failed: {e}")
        
        return None
    
    def _authenticate_session(self, session_cookie: str, ip_address: str,
                             user_agent: str, trace_id: str) -> Optional[User]:
        """Authenticate using session cookie."""
        try:
            # Validate session
            session = self.session_manager.validate_session(session_cookie)
            if not session:
                return None
            
            # Get user
            user = self.security_manager._users_cache.get(session.user_id)
            
            if user and user.is_active and not user.is_locked:
                # Log successful session authentication
                event = AuthEvent(
                    event_type=AuthEventType.LOGIN_SUCCESS,
                    user_id=user.id,
                    username=user.username,
                    session_id=session.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                    trace_id=trace_id,
                    metadata={"auth_method": "session"}
                )
                self.security_manager._log_audit_event(event)
                
                return user
            
        except Exception as e:
            logger.warning(f"Session authentication failed: {e}")
        
        return None
    
    def _log_failed_attempt(self, ip_address: str, user_agent: str, trace_id: str) -> None:
        """Log failed authentication attempt."""
        now = time.time()
        
        # Clean old attempts (older than 1 hour)
        hour_ago = now - 3600
        self._failed_attempts[ip_address] = [
            ts for ts in self._failed_attempts[ip_address] if ts > hour_ago
        ]
        
        # Add current attempt
        self._failed_attempts[ip_address].append(now)
        
        # Log audit event
        event = AuthEvent(
            event_type=AuthEventType.LOGIN_FAILURE,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message="Authentication failed",
            trace_id=trace_id,
            metadata={"failed_attempts": len(self._failed_attempts[ip_address])}
        )
        self.security_manager._log_audit_event(event)


# Decorator for protecting API endpoints
def require_authentication(permission: Optional[Permission] = None):
    """
    Decorator to require authentication and optionally specific permission.
    
    Args:
        permission: Optional required permission.
    
    Returns:
        Decorated function that enforces authentication.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get middleware from arguments or create new instance
            middleware = kwargs.get('security_middleware') or APISecurityMiddleware()
            
            # Extract request info from kwargs
            method = kwargs.get('method', 'GET')
            path = kwargs.get('path', '/api/unknown')
            headers = kwargs.get('headers', {})
            ip_address = kwargs.get('ip_address', '127.0.0.1')
            user_agent = kwargs.get('user_agent', '')
            
            try:
                # Process security
                user = middleware.process_request(method, path, headers, ip_address, user_agent)
                
                # Add user to function arguments
                kwargs['authenticated_user'] = user
                
                return func(*args, **kwargs)
                
            except APISecurityError as e:
                # Return error response
                return middleware.create_error_response(e), e.status_code
        
        return wrapper
    return decorator


# Global API security middleware instance
_api_security_middleware: Optional[APISecurityMiddleware] = None


def get_api_security_middleware() -> APISecurityMiddleware:
    """Get the global API security middleware instance."""
    global _api_security_middleware
    if _api_security_middleware is None:
        _api_security_middleware = APISecurityMiddleware()
    return _api_security_middleware