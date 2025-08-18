"""
JWT (JSON Web Token) security manager with JWKS support and key rotation.

This module provides comprehensive JWT token management with RS256 algorithm,
automatic key rotation, token revocation, and JWKS endpoint support for
secure API authentication.
"""

import json
import logging
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import base64
import hashlib
from dataclasses import dataclass, field

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
    import jwt
    from jwt.exceptions import InvalidTokenError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logging.warning("JWT dependencies not available. Install 'cryptography' and 'pyjwt' packages.")

from .rbac_models import User, AuthEvent, AuthEventType, SecurityConfig, DEFAULT_SECURITY_CONFIG
from .security_manager import get_security_manager

logger = logging.getLogger(__name__)


@dataclass
class JWTKeyPair:
    """JWT key pair with metadata."""
    kid: str  # Key ID
    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class JWTToken:
    """JWT token with metadata."""
    token: str
    token_type: str  # 'access' or 'refresh'
    user_id: str
    expires_at: datetime
    issued_at: datetime = field(default_factory=datetime.utcnow)
    jti: str = field(default_factory=lambda: secrets.token_hex(16))  # JWT ID
    is_revoked: bool = False
    revoked_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class JWTSecurityManager:
    """
    JWT token management with key rotation and revocation support.
    
    Provides secure JWT token generation, validation, and management
    with automatic key rotation, blacklist management, and JWKS support.
    """
    
    def __init__(self, db_path: str = "data/security.db", 
                 config: Optional[SecurityConfig] = None):
        """
        Initialize JWT security manager.
        
        Args:
            db_path: Path to SQLite database for JWT data persistence.
            config: Security configuration (uses default if None).
        """
        if not JWT_AVAILABLE:
            raise RuntimeError("JWT functionality requires 'cryptography' and 'pyjwt' packages")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.config = config or DEFAULT_SECURITY_CONFIG
        self.security_manager = get_security_manager()
        
        self._lock = threading.RLock()
        self._key_pairs: Dict[str, JWTKeyPair] = {}
        self._current_key_id: Optional[str] = None
        self._revoked_tokens: Set[str] = set()  # JTI set for revoked tokens
        
        self._init_database()
        self._load_keys()
        
        # Start key rotation thread
        self._key_rotation_thread = threading.Thread(target=self._key_rotation_worker, daemon=True)
        self._key_rotation_thread.start()
        
        logger.info("JWTSecurityManager initialized")
    
    def _init_database(self) -> None:
        """Initialize SQLite database with JWT tables."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            # JWT key pairs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jwt_keys (
                    kid TEXT PRIMARY KEY,
                    private_key_pem TEXT NOT NULL,
                    public_key_pem TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # JWT tokens table (for tracking and revocation)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jwt_tokens (
                    jti TEXT PRIMARY KEY,
                    token_type TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    issued_at TIMESTAMP NOT NULL,
                    is_revoked BOOLEAN DEFAULT 0,
                    revoked_at TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jwt_tokens_user_id ON jwt_tokens(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jwt_tokens_expires_at ON jwt_tokens(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jwt_keys_active ON jwt_keys(is_active)")
            
            conn.commit()
    
    def generate_key_pair(self) -> JWTKeyPair:
        """
        Generate a new RSA key pair for JWT signing.
        
        Returns:
            New JWT key pair with unique key ID.
        """
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()
        
        # Generate unique key ID
        kid = secrets.token_hex(16)
        
        # Set expiration based on configuration
        expires_at = datetime.utcnow() + timedelta(hours=self.config.jwt_key_rotation_hours * 2)
        
        key_pair = JWTKeyPair(
            kid=kid,
            private_key=private_key,
            public_key=public_key,
            expires_at=expires_at
        )
        
        # Save to database
        self._save_key_pair(key_pair)
        
        logger.info(f"Generated new JWT key pair: {kid}")
        return key_pair
    
    def rotate_keys(self) -> str:
        """
        Rotate JWT signing keys.
        
        Returns:
            Key ID of the new active key.
        """
        with self._lock:
            # Generate new key pair
            new_key_pair = self.generate_key_pair()
            
            # Add to active keys
            self._key_pairs[new_key_pair.kid] = new_key_pair
            
            # Deactivate old keys but keep them for verification
            old_key_id = self._current_key_id
            if old_key_id and old_key_id in self._key_pairs:
                old_key = self._key_pairs[old_key_id]
                old_key.is_active = False
                old_key.expires_at = datetime.utcnow() + timedelta(days=1)  # Keep for 1 day
                self._save_key_pair(old_key)
            
            # Set new key as current
            self._current_key_id = new_key_pair.kid
            
            # Clean up old expired keys
            self._cleanup_expired_keys()
            
            logger.info(f"Rotated JWT keys: {old_key_id} -> {new_key_pair.kid}")
            return new_key_pair.kid
    
    def generate_access_token(self, user: User, additional_claims: Optional[Dict[str, Any]] = None) -> JWTToken:
        """
        Generate JWT access token for user.
        
        Args:
            user: User to generate token for.
            additional_claims: Optional additional JWT claims.
            
        Returns:
            Generated JWT access token.
        """
        with self._lock:
            # Ensure we have an active key
            if not self._current_key_id or self._current_key_id not in self._key_pairs:
                self.rotate_keys()
            
            current_key = self._key_pairs[self._current_key_id]
            
            # Token metadata
            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=self.config.jwt_access_token_expires_minutes)
            jti = secrets.token_hex(16)
            
            # Build JWT claims
            claims = {
                'iss': 'adg-platform',  # Issuer
                'sub': user.id,         # Subject (user ID)
                'aud': 'adg-api',       # Audience
                'exp': int(expires_at.timestamp()),  # Expiration time
                'iat': int(now.timestamp()),         # Issued at
                'jti': jti,             # JWT ID
                'username': user.username,
                'email': user.email,
                'roles': [role.value for role in user.roles],
                'permissions': [perm.value for perm in user.get_all_permissions()],
                'token_type': 'access'
            }
            
            # Add additional claims
            if additional_claims:
                claims.update(additional_claims)
            
            # Generate token
            token = jwt.encode(
                claims,
                current_key.private_key,
                algorithm=self.config.jwt_algorithm,
                headers={'kid': current_key.kid}
            )
            
            # Create token object
            jwt_token = JWTToken(
                token=token,
                token_type='access',
                user_id=user.id,
                expires_at=expires_at,
                jti=jti,
                metadata={'username': user.username, 'roles': [r.value for r in user.roles]}
            )
            
            # Save token metadata
            self._save_token(jwt_token)
            
            # Log audit event
            self._log_jwt_event(user, 'token_generated', 'access', jti)
            
            logger.info(f"Generated access token for user {user.username} (jti: {jti})")
            return jwt_token
    
    def generate_refresh_token(self, user: User, additional_claims: Optional[Dict[str, Any]] = None) -> JWTToken:
        """
        Generate JWT refresh token for user.
        
        Args:
            user: User to generate token for.
            additional_claims: Optional additional JWT claims.
            
        Returns:
            Generated JWT refresh token.
        """
        with self._lock:
            # Ensure we have an active key
            if not self._current_key_id or self._current_key_id not in self._key_pairs:
                self.rotate_keys()
            
            current_key = self._key_pairs[self._current_key_id]
            
            # Token metadata
            now = datetime.utcnow()
            expires_at = now + timedelta(days=self.config.jwt_refresh_token_expires_days)
            jti = secrets.token_hex(16)
            
            # Build JWT claims (minimal for refresh token)
            claims = {
                'iss': 'adg-platform',
                'sub': user.id,
                'aud': 'adg-api',
                'exp': int(expires_at.timestamp()),
                'iat': int(now.timestamp()),
                'jti': jti,
                'username': user.username,
                'token_type': 'refresh'
            }
            
            # Add additional claims
            if additional_claims:
                claims.update(additional_claims)
            
            # Generate token
            token = jwt.encode(
                claims,
                current_key.private_key,
                algorithm=self.config.jwt_algorithm,
                headers={'kid': current_key.kid}
            )
            
            # Create token object
            jwt_token = JWTToken(
                token=token,
                token_type='refresh',
                user_id=user.id,
                expires_at=expires_at,
                jti=jti,
                metadata={'username': user.username}
            )
            
            # Save token metadata
            self._save_token(jwt_token)
            
            # Log audit event
            self._log_jwt_event(user, 'token_generated', 'refresh', jti)
            
            logger.info(f"Generated refresh token for user {user.username} (jti: {jti})")
            return jwt_token
    
    def validate_token(self, token: str, token_type: Optional[str] = None,
                      clock_skew: timedelta = timedelta(minutes=5)) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and return claims.
        
        Args:
            token: JWT token to validate.
            token_type: Expected token type ('access' or 'refresh').
            clock_skew: Allowed clock skew for time validation.
            
        Returns:
            Token claims if valid, None otherwise.
        """
        try:
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            
            if not kid or kid not in self._key_pairs:
                logger.warning(f"JWT token validation failed: unknown key ID {kid}")
                return None
            
            key_pair = self._key_pairs[kid]
            
            # Validate token
            claims = jwt.decode(
                token,
                key_pair.public_key,
                algorithms=[self.config.jwt_algorithm],
                audience='adg-api',
                issuer='adg-platform',
                leeway=clock_skew.total_seconds()
            )
            
            # Check token type if specified
            if token_type and claims.get('token_type') != token_type:
                logger.warning(f"JWT token validation failed: expected {token_type}, got {claims.get('token_type')}")
                return None
            
            # Check if token is revoked
            jti = claims.get('jti')
            if jti and self.is_token_revoked(jti):
                logger.warning(f"JWT token validation failed: token revoked (jti: {jti})")
                return None
            
            return claims
            
        except InvalidTokenError as e:
            logger.warning(f"JWT token validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT token validation error: {e}")
            return None
    
    def revoke_token(self, jti: str, reason: str = "manual_revocation") -> bool:
        """
        Revoke a JWT token by JTI.
        
        Args:
            jti: JWT ID to revoke.
            reason: Reason for revocation.
            
        Returns:
            True if token was revoked, False if not found.
        """
        with self._lock:
            # Add to revoked tokens set
            self._revoked_tokens.add(jti)
            
            # Update database
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    UPDATE jwt_tokens 
                    SET is_revoked = 1, revoked_at = ?
                    WHERE jti = ?
                """, (datetime.utcnow().isoformat(), jti))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Revoked JWT token {jti}: {reason}")
                    return True
            
            return False
    
    def revoke_user_tokens(self, user_id: str, token_type: Optional[str] = None,
                          reason: str = "user_logout") -> int:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User ID whose tokens to revoke.
            token_type: Optional token type to filter ('access' or 'refresh').
            reason: Reason for revocation.
            
        Returns:
            Number of tokens revoked.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get user's active tokens
                query = """
                    SELECT jti FROM jwt_tokens 
                    WHERE user_id = ? AND is_revoked = 0 AND expires_at > ?
                """
                params = [user_id, datetime.utcnow().isoformat()]
                
                if token_type:
                    query += " AND token_type = ?"
                    params.append(token_type)
                
                cursor = conn.execute(query, params)
                tokens = cursor.fetchall()
                
                revoked_count = 0
                for row in tokens:
                    jti = row['jti']
                    if self.revoke_token(jti, reason):
                        revoked_count += 1
                
                logger.info(f"Revoked {revoked_count} tokens for user {user_id}: {reason}")
                return revoked_count
    
    def is_token_revoked(self, jti: str) -> bool:
        """
        Check if a token is revoked.
        
        Args:
            jti: JWT ID to check.
            
        Returns:
            True if token is revoked, False otherwise.
        """
        if jti in self._revoked_tokens:
            return True
        
        # Check database
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT is_revoked FROM jwt_tokens WHERE jti = ?", (jti,)
            )
            row = cursor.fetchone()
            
            if row and row[0]:
                self._revoked_tokens.add(jti)
                return True
        
        return False
    
    def get_jwks(self) -> Dict[str, Any]:
        """
        Get JSON Web Key Set (JWKS) for public key distribution.
        
        Returns:
            JWKS dictionary with public keys.
        """
        with self._lock:
            keys = []
            
            for kid, key_pair in self._key_pairs.items():
                # Get public key numbers for JWK format
                public_numbers = key_pair.public_key.public_numbers()
                
                # Convert to base64url encoding
                n = self._int_to_base64url(public_numbers.n)
                e = self._int_to_base64url(public_numbers.e)
                
                jwk = {
                    'kty': 'RSA',
                    'use': 'sig',
                    'kid': kid,
                    'alg': self.config.jwt_algorithm,
                    'n': n,
                    'e': e
                }
                
                keys.append(jwk)
            
            return {'keys': keys}
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens from database and cache.
        
        Returns:
            Number of tokens cleaned up.
        """
        with self._lock:
            now = datetime.utcnow()
            
            with sqlite3.connect(str(self.db_path)) as conn:
                # Get expired token JTIs
                cursor = conn.execute(
                    "SELECT jti FROM jwt_tokens WHERE expires_at < ?",
                    (now.isoformat(),)
                )
                expired_jtis = [row[0] for row in cursor.fetchall()]
                
                # Remove from revoked tokens cache
                for jti in expired_jtis:
                    self._revoked_tokens.discard(jti)
                
                # Delete from database
                cursor = conn.execute(
                    "DELETE FROM jwt_tokens WHERE expires_at < ?",
                    (now.isoformat(),)
                )
                
                cleanup_count = cursor.rowcount
                conn.commit()
                
                if cleanup_count > 0:
                    logger.info(f"Cleaned up {cleanup_count} expired JWT tokens")
                
                return cleanup_count
    
    def _load_keys(self) -> None:
        """Load JWT keys from database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM jwt_keys ORDER BY created_at DESC")
            
            for row in cursor.fetchall():
                try:
                    # Load private key
                    private_key = serialization.load_pem_private_key(
                        row['private_key_pem'].encode('utf-8'),
                        password=None
                    )
                    
                    # Load public key
                    public_key = serialization.load_pem_public_key(
                        row['public_key_pem'].encode('utf-8')
                    )
                    
                    key_pair = JWTKeyPair(
                        kid=row['kid'],
                        private_key=private_key,
                        public_key=public_key,
                        created_at=datetime.fromisoformat(row['created_at']),
                        expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                        is_active=bool(row['is_active'])
                    )
                    
                    self._key_pairs[key_pair.kid] = key_pair
                    
                    if key_pair.is_active and not self._current_key_id:
                        self._current_key_id = key_pair.kid
                        
                except Exception as e:
                    logger.error(f"Failed to load JWT key {row['kid']}: {e}")
        
        # Generate initial key if none exist
        if not self._key_pairs:
            self.rotate_keys()
        
        logger.info(f"Loaded {len(self._key_pairs)} JWT key pairs")
    
    def _save_key_pair(self, key_pair: JWTKeyPair) -> None:
        """Save JWT key pair to database."""
        # Serialize keys to PEM format
        private_pem = key_pair.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = key_pair.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jwt_keys (
                    kid, private_key_pem, public_key_pem, created_at, expires_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                key_pair.kid, private_pem, public_pem,
                key_pair.created_at.isoformat(),
                key_pair.expires_at.isoformat() if key_pair.expires_at else None,
                key_pair.is_active
            ))
            conn.commit()
    
    def _save_token(self, jwt_token: JWTToken) -> None:
        """Save JWT token metadata to database."""
        metadata_json = json.dumps(jwt_token.metadata)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jwt_tokens (
                    jti, token_type, user_id, expires_at, issued_at,
                    is_revoked, revoked_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                jwt_token.jti, jwt_token.token_type, jwt_token.user_id,
                jwt_token.expires_at.isoformat(), jwt_token.issued_at.isoformat(),
                jwt_token.is_revoked,
                jwt_token.revoked_at.isoformat() if jwt_token.revoked_at else None,
                metadata_json
            ))
            conn.commit()
    
    def _cleanup_expired_keys(self) -> None:
        """Clean up expired JWT keys."""
        now = datetime.utcnow()
        expired_keys = []
        
        for kid, key_pair in list(self._key_pairs.items()):
            if key_pair.expires_at and now > key_pair.expires_at:
                expired_keys.append(kid)
        
        for kid in expired_keys:
            del self._key_pairs[kid]
            
            # Delete from database
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM jwt_keys WHERE kid = ?", (kid,))
                conn.commit()
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired JWT keys")
    
    def _int_to_base64url(self, value: int) -> str:
        """Convert integer to base64url encoding."""
        # Convert to bytes with proper padding
        byte_length = (value.bit_length() + 7) // 8
        bytes_value = value.to_bytes(byte_length, 'big')
        
        # Base64url encode
        encoded = base64.urlsafe_b64encode(bytes_value).decode('utf-8')
        return encoded.rstrip('=')  # Remove padding
    
    def _log_jwt_event(self, user: User, action: str, token_type: str, jti: str) -> None:
        """Log JWT-related audit event."""
        event = AuthEvent(
            event_type=AuthEventType.LOGIN_SUCCESS,  # Use appropriate event type
            user_id=user.id,
            username=user.username,
            ip_address="127.0.0.1",  # Default for internal operations
            success=True,
            metadata={
                'jwt_action': action,
                'token_type': token_type,
                'jti': jti,
                'key_id': self._current_key_id
            }
        )
        
        self.security_manager._log_audit_event(event)
    
    def _key_rotation_worker(self) -> None:
        """Background worker for automatic key rotation."""
        while True:
            try:
                # Sleep for rotation interval
                rotation_hours = self.config.jwt_key_rotation_hours
                time.sleep(rotation_hours * 3600)  # Convert to seconds
                
                # Rotate keys
                self.rotate_keys()
                
                # Cleanup expired tokens
                self.cleanup_expired_tokens()
                
            except Exception as e:
                logger.error(f"JWT key rotation worker error: {e}")
                time.sleep(3600)  # Wait 1 hour before retrying


# Global JWT security manager instance
_jwt_manager: Optional[JWTSecurityManager] = None


def get_jwt_manager() -> JWTSecurityManager:
    """Get the global JWT security manager instance."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTSecurityManager()
    return _jwt_manager