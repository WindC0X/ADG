"""
Core security management system for the ADG platform.

This module provides centralized authentication, authorization, and security
services with PBKDF2 password hashing, session management, and audit logging.
"""

import hashlib
import hmac
import logging
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from .rbac_models import (
    User, Session, AuthEvent, SecurityConfig, Permission, Role,
    AuthEventType, SessionStatus, DEFAULT_SECURITY_CONFIG
)
from .feature_manager import get_feature_manager
from core.node_interfaces import ValidationResult, ValidationSeverity

logger = logging.getLogger(__name__)


class PasswordHasher:
    """PBKDF2 password hashing with salt generation and verification."""
    
    def __init__(self, iterations: int = 100000, hash_name: str = 'sha256'):
        """
        Initialize password hasher with security parameters.
        
        Args:
            iterations: Number of PBKDF2 iterations (minimum 100000 for security).
            hash_name: Hash algorithm name ('sha256' recommended).
        """
        if iterations < 50000:
            raise ValueError("PBKDF2 iterations must be at least 50000 for security")
        
        self.iterations = iterations
        self.hash_name = hash_name
        self.salt_length = 32  # 256-bit salt
        
    def generate_salt(self) -> str:
        """Generate a cryptographically secure random salt."""
        return secrets.token_hex(self.salt_length)
    
    def hash_password(self, password: str, salt: str) -> str:
        """
        Hash a password using PBKDF2 with the provided salt.
        
        Args:
            password: Plain text password to hash.
            salt: Hex-encoded salt string.
            
        Returns:
            Hex-encoded password hash.
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        if not salt:
            raise ValueError("Salt cannot be empty")
        
        # Convert hex salt to bytes
        try:
            salt_bytes = bytes.fromhex(salt)
        except ValueError:
            raise ValueError("Salt must be a valid hex string")
        
        # Generate PBKDF2 hash
        password_bytes = password.encode('utf-8')
        hash_bytes = hashlib.pbkdf2_hmac(
            self.hash_name, password_bytes, salt_bytes, self.iterations
        )
        
        return hash_bytes.hex()
    
    def verify_password(self, password: str, salt: str, stored_hash: str) -> bool:
        """
        Verify a password against its stored hash and salt.
        
        Args:
            password: Plain text password to verify.
            salt: Hex-encoded salt string.
            stored_hash: Hex-encoded stored password hash.
            
        Returns:
            True if password matches, False otherwise.
        """
        try:
            computed_hash = self.hash_password(password, salt)
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(computed_hash, stored_hash)
        except Exception as e:
            logger.warning(f"Password verification failed: {e}")
            return False
    
    def validate_password_strength(self, password: str, config: SecurityConfig) -> List[ValidationResult]:
        """
        Validate password strength against security policy.
        
        Args:
            password: Password to validate.
            config: Security configuration with password policy.
            
        Returns:
            List of validation results.
        """
        results = []
        
        # Length check
        if len(password) < config.min_password_length:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Password must be at least {config.min_password_length} characters long",
                field_name="password",
                error_code="PASSWORD_TOO_SHORT"
            ))
        
        # Character requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if config.require_uppercase and not has_upper:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Password must contain at least one uppercase letter",
                field_name="password",
                error_code="PASSWORD_NO_UPPERCASE"
            ))
        
        if config.require_lowercase and not has_lower:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Password must contain at least one lowercase letter",
                field_name="password",
                error_code="PASSWORD_NO_LOWERCASE"
            ))
        
        if config.require_digits and not has_digit:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Password must contain at least one digit",
                field_name="password",
                error_code="PASSWORD_NO_DIGIT"
            ))
        
        if config.require_special_chars and not has_special:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Password must contain at least one special character",
                field_name="password",
                error_code="PASSWORD_NO_SPECIAL"
            ))
        
        return results


class SecurityManager:
    """
    Core security manager for authentication, authorization, and audit logging.
    
    Provides centralized security services with database persistence,
    feature flag integration, and comprehensive audit logging.
    """
    
    def __init__(self, db_path: str = "data/security.db", 
                 config: Optional[SecurityConfig] = None):
        """
        Initialize security manager.
        
        Args:
            db_path: Path to SQLite database for security data.
            config: Security configuration (uses default if None).
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.config = config or DEFAULT_SECURITY_CONFIG
        self.password_hasher = PasswordHasher()
        self.feature_manager = get_feature_manager()
        
        self._lock = threading.RLock()
        self._sessions_cache: Dict[str, Session] = {}
        self._users_cache: Dict[str, User] = {}
        
        self._init_database()
        logger.info("SecurityManager initialized")
    
    def _init_database(self) -> None:
        """Initialize SQLite database with security tables."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    roles TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    is_locked BOOLEAN DEFAULT 0,
                    failed_login_attempts INTEGER DEFAULT 0,
                    last_login TIMESTAMP,
                    last_password_change TIMESTAMP NOT NULL,
                    password_expires_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    metadata TEXT
                )
            """)
            
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    csrf_token TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    user_agent TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    last_activity TIMESTAMP NOT NULL,
                    activity_timeout_seconds INTEGER NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            
            # Audit events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    username TEXT,
                    session_id TEXT,
                    ip_address TEXT NOT NULL,
                    user_agent TEXT,
                    resource TEXT,
                    permission TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    trace_id TEXT NOT NULL,
                    metadata TEXT,
                    hash_chain TEXT
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON audit_events(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp)")
            
            conn.commit()
    
    def create_user(self, username: str, email: str, password: str, 
                   roles: Set[Role], **kwargs) -> User:
        """
        Create a new user with secure password storage.
        
        Args:
            username: Unique username.
            email: Unique email address.
            password: Plain text password.
            roles: Set of roles to assign.
            **kwargs: Additional user properties.
            
        Returns:
            Created user object.
            
        Raises:
            ValueError: If validation fails or user already exists.
        """
        with self._lock:
            # Validate password strength
            password_validation = self.password_hasher.validate_password_strength(
                password, self.config
            )
            
            validation_errors = [r for r in password_validation if not r.is_valid]
            if validation_errors:
                error_messages = [r.message for r in validation_errors]
                raise ValueError(f"Password validation failed: {'; '.join(error_messages)}")
            
            # Generate salt and hash password
            salt = self.password_hasher.generate_salt()
            password_hash = self.password_hasher.hash_password(password, salt)
            
            # Create user object
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                salt=salt,
                roles=roles,
                **kwargs
            )
            
            # Validate user data
            user_validation = user.validate()
            validation_errors = [r for r in user_validation if not r.is_valid]
            if validation_errors:
                error_messages = [r.message for r in validation_errors]
                raise ValueError(f"User validation failed: {'; '.join(error_messages)}")
            
            # Save to database
            self._save_user_to_db(user)
            self._users_cache[user.id] = user
            
            # Log audit event
            self._log_audit_event(AuthEvent(
                event_type=AuthEventType.LOGIN_SUCCESS,
                user_id=user.id,
                username=user.username,
                ip_address="127.0.0.1",  # Default for user creation
                success=True,
                metadata={"action": "user_created", "roles": [r.value for r in roles]}
            ))
            
            logger.info(f"Created user '{username}' with roles {[r.value for r in roles]}")
            return user
    
    def authenticate_user(self, username: str, password: str, 
                         ip_address: str, user_agent: str = "") -> Optional[User]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: Username to authenticate.
            password: Plain text password.
            ip_address: Client IP address for audit logging.
            user_agent: Client user agent string.
            
        Returns:
            User object if authentication successful, None otherwise.
        """
        with self._lock:
            user = self._get_user_by_username(username)
            
            if not user:
                # Log failed authentication attempt
                self._log_audit_event(AuthEvent(
                    event_type=AuthEventType.LOGIN_FAILURE,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message="User not found"
                ))
                return None
            
            # Check if account is locked
            if user.is_locked:
                self._log_audit_event(AuthEvent(
                    event_type=AuthEventType.LOGIN_FAILURE,
                    user_id=user.id,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message="Account locked"
                ))
                return None
            
            # Check if account is active
            if not user.is_active:
                self._log_audit_event(AuthEvent(
                    event_type=AuthEventType.LOGIN_FAILURE,
                    user_id=user.id,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message="Account inactive"
                ))
                return None
            
            # Verify password
            if not self.password_hasher.verify_password(password, user.salt, user.password_hash):
                # Increment failed attempts
                user.increment_failed_attempts()
                
                # Lock account if too many failed attempts
                if user.should_lock_account(self.config.max_failed_attempts):
                    user.is_locked = True
                    self._save_user_to_db(user)
                    self._users_cache[user.id] = user
                    
                    self._log_audit_event(AuthEvent(
                        event_type=AuthEventType.ACCOUNT_LOCKED,
                        user_id=user.id,
                        username=username,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                        error_message=f"Account locked after {user.failed_login_attempts} failed attempts"
                    ))
                else:
                    self._save_user_to_db(user)
                    self._users_cache[user.id] = user
                
                self._log_audit_event(AuthEvent(
                    event_type=AuthEventType.LOGIN_FAILURE,
                    user_id=user.id,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message="Invalid password"
                ))
                return None
            
            # Check password expiration
            if user.is_password_expired():
                self._log_audit_event(AuthEvent(
                    event_type=AuthEventType.LOGIN_FAILURE,
                    user_id=user.id,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message="Password expired"
                ))
                return None
            
            # Successful authentication - reset failed attempts
            user.reset_failed_attempts()
            user.last_login = datetime.utcnow()
            self._save_user_to_db(user)
            self._users_cache[user.id] = user
            
            self._log_audit_event(AuthEvent(
                event_type=AuthEventType.LOGIN_SUCCESS,
                user_id=user.id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            ))
            
            logger.info(f"User '{username}' authenticated successfully from {ip_address}")
            return user
    
    def _get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username from cache or database."""
        # Check cache first
        for user in self._users_cache.values():
            if user.username == username:
                return user
        
        # Load from database
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            
            if row:
                user = self._user_from_row(row)
                self._users_cache[user.id] = user
                return user
        
        return None
    
    def _user_from_row(self, row: sqlite3.Row) -> User:
        """Convert database row to User object."""
        import json
        
        roles_str = row['roles']
        roles = {Role(role) for role in json.loads(roles_str)}
        
        metadata = {}
        if row['metadata']:
            metadata = json.loads(row['metadata'])
        
        return User(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            password_hash=row['password_hash'],
            salt=row['salt'],
            roles=roles,
            is_active=bool(row['is_active']),
            is_locked=bool(row['is_locked']),
            failed_login_attempts=row['failed_login_attempts'],
            last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
            last_password_change=datetime.fromisoformat(row['last_password_change']),
            password_expires_at=datetime.fromisoformat(row['password_expires_at']) if row['password_expires_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            metadata=metadata
        )
    
    def _save_user_to_db(self, user: User) -> None:
        """Save user to database."""
        import json
        
        roles_json = json.dumps([role.value for role in user.roles])
        metadata_json = json.dumps(user.metadata)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO users (
                    id, username, email, password_hash, salt, roles,
                    is_active, is_locked, failed_login_attempts,
                    last_login, last_password_change, password_expires_at,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user.id, user.username, user.email, user.password_hash, user.salt, roles_json,
                user.is_active, user.is_locked, user.failed_login_attempts,
                user.last_login.isoformat() if user.last_login else None,
                user.last_password_change.isoformat(),
                user.password_expires_at.isoformat() if user.password_expires_at else None,
                user.created_at.isoformat(), user.updated_at.isoformat(), metadata_json
            ))
            conn.commit()
    
    def _log_audit_event(self, event: AuthEvent) -> None:
        """Log audit event to database."""
        import json
        
        metadata_json = json.dumps(event.metadata)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO audit_events (
                    id, event_type, user_id, username, session_id,
                    ip_address, user_agent, resource, permission,
                    success, error_message, timestamp, trace_id,
                    metadata, hash_chain
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id, event.event_type.value, event.user_id, event.username, event.session_id,
                event.ip_address, event.user_agent, event.resource,
                event.permission.value if event.permission else None,
                event.success, event.error_message, event.timestamp.isoformat(), event.trace_id,
                metadata_json, event.hash_chain
            ))
            conn.commit()


# Global security manager instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager