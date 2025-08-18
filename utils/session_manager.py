"""
Session management system with CSRF protection and security policies.

This module provides secure session lifecycle management with timeout handling,
concurrency limits, fixation protection, and comprehensive audit logging.
"""

import logging
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from .rbac_models import Session, User, AuthEvent, SessionStatus, AuthEventType
from .security_manager import get_security_manager

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages user sessions with security features and audit logging.
    
    Provides session creation, validation, cleanup, and security policies
    including CSRF protection, timeout handling, and concurrency limits.
    """
    
    def __init__(self, db_path: str = "data/security.db"):
        """
        Initialize session manager.
        
        Args:
            db_path: Path to SQLite database for session persistence.
        """
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._active_sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> session_ids
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        logger.info("SessionManager initialized")
    
    def create_session(self, user: User, ip_address: str, 
                      user_agent: str = "", metadata: Optional[Dict[str, Any]] = None) -> Session:
        """
        Create a new session for the authenticated user.
        
        Args:
            user: Authenticated user object.
            ip_address: Client IP address.
            user_agent: Client user agent string.
            metadata: Optional session metadata.
            
        Returns:
            Created session object.
            
        Raises:
            ValueError: If session limits exceeded or user invalid.
        """
        with self._lock:
            if not user.is_active:
                raise ValueError("Cannot create session for inactive user")
            
            if user.is_locked:
                raise ValueError("Cannot create session for locked user")
            
            # Check concurrent session limits
            user_sessions = self._user_sessions.get(user.id, set())
            active_count = len([sid for sid in user_sessions 
                              if sid in self._active_sessions and self._active_sessions[sid].is_active()])
            
            security_manager = get_security_manager()
            max_sessions = security_manager.config.max_concurrent_sessions
            
            if active_count >= max_sessions:
                # Revoke oldest session
                oldest_session_id = min(user_sessions, 
                                      key=lambda sid: self._active_sessions.get(sid, Session()).created_at)
                if oldest_session_id in self._active_sessions:
                    self.revoke_session(oldest_session_id, "concurrent_limit_exceeded")
            
            # Create new session
            session_timeout = timedelta(hours=security_manager.config.session_timeout_hours)
            activity_timeout = timedelta(hours=security_manager.config.activity_timeout_hours)
            
            session = Session(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=datetime.utcnow() + session_timeout,
                activity_timeout=activity_timeout,
                metadata=metadata or {}
            )
            
            # Implement session fixation protection
            self._protect_against_fixation(session, user)
            
            # Save to database and cache
            self._save_session_to_db(session)
            self._active_sessions[session.id] = session
            
            if user.id not in self._user_sessions:
                self._user_sessions[user.id] = set()
            self._user_sessions[user.id].add(session.id)
            
            # Log audit event
            self._log_session_event(session, AuthEventType.LOGIN_SUCCESS, user.username)
            
            logger.info(f"Created session {session.id} for user {user.username} from {ip_address}")
            return session
    
    def validate_session(self, session_token: str, update_activity: bool = True) -> Optional[Session]:
        """
        Validate and optionally update session activity.
        
        Args:
            session_token: Session token to validate.
            update_activity: Whether to update last activity timestamp.
            
        Returns:
            Valid session object or None if invalid/expired.
        """
        with self._lock:
            session = self._get_session_by_token(session_token)
            
            if not session:
                return None
            
            if not session.is_active():
                # Session expired or revoked
                if session.status == SessionStatus.ACTIVE:
                    # Update status to expired
                    session.status = SessionStatus.EXPIRED
                    self._save_session_to_db(session)
                    self._log_session_event(session, AuthEventType.SESSION_EXPIRED)
                
                return None
            
            if update_activity:
                session.update_activity()
                self._save_session_to_db(session)
                self._active_sessions[session.id] = session
            
            return session
    
    def validate_csrf_token(self, session_token: str, csrf_token: str) -> bool:
        """
        Validate CSRF token for the session.
        
        Args:
            session_token: Session token.
            csrf_token: CSRF token to validate.
            
        Returns:
            True if CSRF token is valid, False otherwise.
        """
        session = self.validate_session(session_token, update_activity=False)
        if not session:
            return False
        
        return session.validate_csrf(csrf_token)
    
    def revoke_session(self, session_id: str, reason: str = "manual_revocation") -> bool:
        """
        Revoke a session.
        
        Args:
            session_id: Session ID to revoke.
            reason: Reason for revocation.
            
        Returns:
            True if session was revoked, False if not found.
        """
        with self._lock:
            session = self._active_sessions.get(session_id)
            if not session:
                # Try to load from database
                session = self._get_session_by_id(session_id)
                if not session:
                    return False
            
            if session.status == SessionStatus.ACTIVE:
                session.revoke()
                session.metadata["revocation_reason"] = reason
                session.metadata["revoked_at"] = datetime.utcnow().isoformat()
                
                self._save_session_to_db(session)
                self._active_sessions[session.id] = session
                
                self._log_session_event(session, AuthEventType.SESSION_REVOKED, 
                                      metadata={"reason": reason})
                
                logger.info(f"Revoked session {session_id}: {reason}")
            
            return True
    
    def revoke_user_sessions(self, user_id: str, exclude_session_id: Optional[str] = None,
                           reason: str = "user_logout") -> int:
        """
        Revoke all sessions for a user.
        
        Args:
            user_id: User ID whose sessions to revoke.
            exclude_session_id: Optional session ID to exclude from revocation.
            reason: Reason for revocation.
            
        Returns:
            Number of sessions revoked.
        """
        with self._lock:
            user_sessions = self._user_sessions.get(user_id, set()).copy()
            revoked_count = 0
            
            for session_id in user_sessions:
                if session_id != exclude_session_id:
                    if self.revoke_session(session_id, reason):
                        revoked_count += 1
            
            return revoked_count
    
    def extend_session(self, session_token: str, hours: int = 8) -> bool:
        """
        Extend session expiry time.
        
        Args:
            session_token: Session token to extend.
            hours: Number of hours to extend.
            
        Returns:
            True if session was extended, False if invalid.
        """
        with self._lock:
            session = self.validate_session(session_token, update_activity=True)
            if not session:
                return False
            
            session.extend_expiry(hours)
            self._save_session_to_db(session)
            self._active_sessions[session.id] = session
            
            self._log_session_event(session, AuthEventType.LOGIN_SUCCESS,
                                  metadata={"action": "session_extended", "hours": hours})
            
            logger.info(f"Extended session {session.id} by {hours} hours")
            return True
    
    def get_user_sessions(self, user_id: str, active_only: bool = True) -> List[Session]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User ID to get sessions for.
            active_only: Whether to return only active sessions.
            
        Returns:
            List of session objects.
        """
        with self._lock:
            sessions = []
            user_sessions = self._user_sessions.get(user_id, set())
            
            for session_id in user_sessions:
                session = self._active_sessions.get(session_id)
                if not session:
                    session = self._get_session_by_id(session_id)
                
                if session:
                    if not active_only or session.is_active():
                        sessions.append(session)
            
            return sorted(sessions, key=lambda s: s.created_at, reverse=True)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up.
        """
        with self._lock:
            expired_sessions = []
            
            # Check cached sessions
            for session_id, session in list(self._active_sessions.items()):
                if not session.is_active():
                    expired_sessions.append(session)
            
            # Clean up expired sessions
            cleanup_count = 0
            for session in expired_sessions:
                if session.status == SessionStatus.ACTIVE:
                    session.status = SessionStatus.EXPIRED
                    self._save_session_to_db(session)
                    self._log_session_event(session, AuthEventType.SESSION_EXPIRED)
                
                # Remove from cache
                if session.id in self._active_sessions:
                    del self._active_sessions[session.id]
                
                # Remove from user sessions
                if session.user_id in self._user_sessions:
                    self._user_sessions[session.user_id].discard(session.id)
                    if not self._user_sessions[session.user_id]:
                        del self._user_sessions[session.user_id]
                
                cleanup_count += 1
            
            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} expired sessions")
            
            return cleanup_count
    
    def _protect_against_fixation(self, session: Session, user: User) -> None:
        """
        Implement session fixation protection.
        
        Args:
            session: New session to protect.
            user: User for the session.
        """
        # Regenerate session token after authentication
        session.session_token = secrets.token_urlsafe(32)
        session.csrf_token = secrets.token_urlsafe(16)
        
        # Add fixation protection metadata
        session.metadata.update({
            "fixation_protection": True,
            "token_regenerated_at": datetime.utcnow().isoformat(),
            "user_agent_hash": str(hash(session.user_agent))
        })
    
    def _get_session_by_token(self, session_token: str) -> Optional[Session]:
        """Get session by token from cache or database."""
        # Check cache first
        for session in self._active_sessions.values():
            if session.session_token == session_token:
                return session
        
        # Load from database
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE session_token = ?", (session_token,)
            )
            row = cursor.fetchone()
            
            if row:
                session = self._session_from_row(row)
                self._active_sessions[session.id] = session
                
                # Update user sessions cache
                if session.user_id not in self._user_sessions:
                    self._user_sessions[session.user_id] = set()
                self._user_sessions[session.user_id].add(session.id)
                
                return session
        
        return None
    
    def _get_session_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by ID from database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._session_from_row(row)
        
        return None
    
    def _session_from_row(self, row: sqlite3.Row) -> Session:
        """Convert database row to Session object."""
        import json
        
        metadata = {}
        if row['metadata']:
            metadata = json.loads(row['metadata'])
        
        return Session(
            id=row['id'],
            user_id=row['user_id'],
            session_token=row['session_token'],
            csrf_token=row['csrf_token'],
            ip_address=row['ip_address'],
            user_agent=row['user_agent'] or "",
            status=SessionStatus[row['status']],
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']),
            last_activity=datetime.fromisoformat(row['last_activity']),
            activity_timeout=timedelta(seconds=row['activity_timeout_seconds']),
            metadata=metadata
        )
    
    def _save_session_to_db(self, session: Session) -> None:
        """Save session to database."""
        import json
        
        metadata_json = json.dumps(session.metadata)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions (
                    id, user_id, session_token, csrf_token, ip_address,
                    user_agent, status, created_at, expires_at,
                    last_activity, activity_timeout_seconds, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.id, session.user_id, session.session_token, session.csrf_token,
                session.ip_address, session.user_agent, session.status.name,
                session.created_at.isoformat(), session.expires_at.isoformat(),
                session.last_activity.isoformat(), int(session.activity_timeout.total_seconds()),
                metadata_json
            ))
            conn.commit()
    
    def _log_session_event(self, session: Session, event_type: AuthEventType, 
                          username: Optional[str] = None, 
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log session-related audit event."""
        security_manager = get_security_manager()
        
        event = AuthEvent(
            event_type=event_type,
            user_id=session.user_id,
            username=username,
            session_id=session.id,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            success=True,
            metadata=metadata or {}
        )
        
        security_manager._log_audit_event(event)
    
    def _cleanup_worker(self) -> None:
        """Background worker for session cleanup."""
        import time
        
        while True:
            try:
                # Run cleanup every 5 minutes
                time.sleep(300)
                self.cleanup_expired_sessions()
                
            except Exception as e:
                logger.error(f"Session cleanup worker error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager