"""
Enhanced audit logging system with tamper-proof hash chains and security monitoring.

This module provides comprehensive audit logging with integrity verification,
trace ID tracking, security event monitoring, and compliance reporting for
the ADG security system.
"""

import hashlib
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, Callable
from collections import defaultdict
from dataclasses import asdict

from .rbac_models import AuthEvent, AuthEventType, User
from .security_manager import get_security_manager

logger = logging.getLogger(__name__)


class SecurityIncident:
    """Security incident data structure."""
    def __init__(self, incident_type: str, severity: str, user_id: Optional[str] = None,
                 ip_address: str = "", description: str = "", 
                 evidence: Optional[Dict[str, Any]] = None):
        self.incident_id = f"INC-{int(time.time())}-{hash(description) % 10000:04d}"
        self.incident_type = incident_type
        self.severity = severity  # LOW, MEDIUM, HIGH, CRITICAL
        self.user_id = user_id
        self.ip_address = ip_address
        self.description = description
        self.evidence = evidence or {}
        self.detected_at = datetime.utcnow()
        self.status = "OPEN"  # OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE
        self.assigned_to: Optional[str] = None
        self.resolution_notes: Optional[str] = None
        self.resolved_at: Optional[datetime] = None


class AuditLogger:
    """
    Enhanced audit logging system with tamper-proof hash chains.
    
    Provides secure audit logging with integrity verification, trace ID
    tracking, and comprehensive security event recording for compliance
    and forensic analysis.
    """
    
    def __init__(self, db_path: str = "data/security.db"):
        """
        Initialize audit logger.
        
        Args:
            db_path: Path to SQLite database for audit data.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        self._last_hash: Optional[str] = None
        self._event_count = 0
        
        self._init_audit_database()
        self._load_last_hash()
        
        logger.info("AuditLogger initialized")
    
    def _init_audit_database(self) -> None:
        """Initialize audit database tables."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            # Enhanced audit events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events_enhanced (
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
                    hash_chain TEXT NOT NULL,
                    previous_hash TEXT,
                    event_sequence INTEGER NOT NULL,
                    integrity_verified BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Audit trail verification table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_verification (
                    verification_id TEXT PRIMARY KEY,
                    start_sequence INTEGER NOT NULL,
                    end_sequence INTEGER NOT NULL,
                    expected_hash TEXT NOT NULL,
                    actual_hash TEXT NOT NULL,
                    verification_passed BOOLEAN NOT NULL,
                    verified_at TIMESTAMP NOT NULL,
                    verified_by TEXT,
                    notes TEXT
                )
            """)
            
            # Security incidents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_incidents (
                    incident_id TEXT PRIMARY KEY,
                    incident_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    user_id TEXT,
                    ip_address TEXT,
                    description TEXT NOT NULL,
                    evidence TEXT,
                    detected_at TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'OPEN',
                    assigned_to TEXT,
                    resolution_notes TEXT,
                    resolved_at TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_enhanced_timestamp ON audit_events_enhanced(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_enhanced_user ON audit_events_enhanced(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_enhanced_trace ON audit_events_enhanced(trace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_enhanced_sequence ON audit_events_enhanced(event_sequence)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_severity ON security_incidents(severity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON security_incidents(status)")
            
            conn.commit()
    
    def log_security_event(self, event: AuthEvent) -> str:
        """
        Log security event with tamper-proof hash chain.
        
        Args:
            event: Security event to log.
            
        Returns:
            Event hash for verification.
        """
        with self._lock:
            self._event_count += 1
            
            # Calculate event hash with chain integrity
            event_data = self._prepare_event_data(event)
            event_hash = self._calculate_event_hash(event_data, self._last_hash)
            
            # Save to database with hash chain
            self._save_event_to_database(event, event_hash, self._last_hash, self._event_count)
            
            # Update hash chain
            self._last_hash = event_hash
            
            # Trigger security monitoring
            self._check_security_patterns(event)
            
            logger.debug(f"Logged security event {event.id} with hash {event_hash[:16]}...")
            return event_hash
    
    def verify_audit_integrity(self, start_sequence: int = 1, 
                             end_sequence: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify integrity of audit trail using hash chain.
        
        Args:
            start_sequence: Starting sequence number.
            end_sequence: Ending sequence number (None for latest).
            
        Returns:
            Verification result with details.
        """
        with self._lock:
            if end_sequence is None:
                end_sequence = self._event_count
            
            verification_id = f"VER-{int(time.time())}"
            verification_passed = True
            broken_chains = []
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT * FROM audit_events_enhanced 
                    WHERE event_sequence BETWEEN ? AND ? 
                    ORDER BY event_sequence
                """, (start_sequence, end_sequence))
                
                events = cursor.fetchall()
                previous_hash = None
                
                for event in events:
                    # Reconstruct event data
                    event_data = {
                        'id': event['id'],
                        'event_type': event['event_type'],
                        'user_id': event['user_id'],
                        'username': event['username'],
                        'session_id': event['session_id'],
                        'ip_address': event['ip_address'],
                        'user_agent': event['user_agent'],
                        'resource': event['resource'],
                        'permission': event['permission'],
                        'success': bool(event['success']),
                        'error_message': event['error_message'],
                        'timestamp': event['timestamp'],
                        'trace_id': event['trace_id'],
                        'metadata': event['metadata']
                    }
                    
                    # Calculate expected hash
                    expected_hash = self._calculate_event_hash(event_data, previous_hash)
                    actual_hash = event['hash_chain']
                    
                    if expected_hash != actual_hash:
                        verification_passed = False
                        broken_chains.append({
                            'sequence': event['event_sequence'],
                            'event_id': event['id'],
                            'expected_hash': expected_hash,
                            'actual_hash': actual_hash,
                            'timestamp': event['timestamp']
                        })
                    
                    previous_hash = actual_hash
                
                # Save verification result
                conn.execute("""
                    INSERT INTO audit_verification (
                        verification_id, start_sequence, end_sequence,
                        expected_hash, actual_hash, verification_passed,
                        verified_at, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    verification_id, start_sequence, end_sequence,
                    previous_hash or "", previous_hash or "",
                    verification_passed, datetime.utcnow().isoformat(),
                    f"Verified {len(events)} events, {len(broken_chains)} integrity violations"
                ))
                conn.commit()
            
            result = {
                'verification_id': verification_id,
                'start_sequence': start_sequence,
                'end_sequence': end_sequence,
                'events_verified': len(events),
                'verification_passed': verification_passed,
                'integrity_violations': len(broken_chains),
                'broken_chains': broken_chains,
                'verified_at': datetime.utcnow().isoformat()
            }
            
            if not verification_passed:
                logger.error(f"Audit integrity verification failed: {len(broken_chains)} violations found")
            else:
                logger.info(f"Audit integrity verification passed for {len(events)} events")
            
            return result
    
    def search_audit_events(self, filters: Dict[str, Any], 
                           limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Search audit events with filters.
        
        Args:
            filters: Search filters (user_id, event_type, start_time, end_time, etc.).
            limit: Maximum number of results.
            
        Returns:
            List of matching audit events.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            
            query_parts = ["SELECT * FROM audit_events_enhanced WHERE 1=1"]
            params = []
            
            # Apply filters
            if 'user_id' in filters:
                query_parts.append("AND user_id = ?")
                params.append(filters['user_id'])
            
            if 'event_type' in filters:
                query_parts.append("AND event_type = ?")
                params.append(filters['event_type'])
            
            if 'ip_address' in filters:
                query_parts.append("AND ip_address = ?")
                params.append(filters['ip_address'])
            
            if 'start_time' in filters:
                query_parts.append("AND timestamp >= ?")
                params.append(filters['start_time'])
            
            if 'end_time' in filters:
                query_parts.append("AND timestamp <= ?")
                params.append(filters['end_time'])
            
            if 'trace_id' in filters:
                query_parts.append("AND trace_id = ?")
                params.append(filters['trace_id'])
            
            if 'success' in filters:
                query_parts.append("AND success = ?")
                params.append(filters['success'])
            
            query_parts.append("ORDER BY timestamp DESC LIMIT ?")
            params.append(limit)
            
            query = " ".join(query_parts)
            cursor = conn.execute(query, params)
            
            events = []
            for row in cursor.fetchall():
                event_dict = dict(row)
                if event_dict['metadata']:
                    event_dict['metadata'] = json.loads(event_dict['metadata'])
                events.append(event_dict)
            
            return events
    
    def generate_compliance_report(self, start_date: datetime, end_date: datetime,
                                 report_type: str = "security") -> Dict[str, Any]:
        """
        Generate compliance report for audit events.
        
        Args:
            start_date: Report start date.
            end_date: Report end date.
            report_type: Type of report (security, access, authentication).
            
        Returns:
            Compliance report data.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            
            # Base statistics
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_events,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_events,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_events,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT ip_address) as unique_ips,
                    COUNT(DISTINCT trace_id) as unique_traces
                FROM audit_events_enhanced 
                WHERE timestamp BETWEEN ? AND ?
            """, (start_date.isoformat(), end_date.isoformat()))
            
            stats = dict(cursor.fetchone())
            
            # Event type breakdown
            cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_events_enhanced 
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY event_type
                ORDER BY count DESC
            """, (start_date.isoformat(), end_date.isoformat()))
            
            event_types = [dict(row) for row in cursor.fetchall()]
            
            # Failed authentication attempts
            cursor = conn.execute("""
                SELECT ip_address, COUNT(*) as failed_attempts
                FROM audit_events_enhanced 
                WHERE timestamp BETWEEN ? AND ? 
                AND event_type = 'auth.login.failure'
                GROUP BY ip_address
                HAVING failed_attempts > 5
                ORDER BY failed_attempts DESC
            """, (start_date.isoformat(), end_date.isoformat()))
            
            suspicious_ips = [dict(row) for row in cursor.fetchall()]
            
            # Permission violations
            cursor = conn.execute("""
                SELECT user_id, username, COUNT(*) as violations
                FROM audit_events_enhanced 
                WHERE timestamp BETWEEN ? AND ? 
                AND event_type = 'auth.permission.denied'
                GROUP BY user_id, username
                ORDER BY violations DESC
                LIMIT 20
            """, (start_date.isoformat(), end_date.isoformat()))
            
            permission_violations = [dict(row) for row in cursor.fetchall()]
            
            # Security incidents
            cursor = conn.execute("""
                SELECT severity, COUNT(*) as count
                FROM security_incidents
                WHERE detected_at BETWEEN ? AND ?
                GROUP BY severity
            """, (start_date.isoformat(), end_date.isoformat()))
            
            incidents_by_severity = [dict(row) for row in cursor.fetchall()]
            
            # Verify audit integrity for report period
            integrity_check = self.verify_audit_integrity()
            
            report = {
                'report_type': report_type,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'generated_at': datetime.utcnow().isoformat(),
                'statistics': stats,
                'event_breakdown': event_types,
                'security_issues': {
                    'suspicious_ips': suspicious_ips,
                    'permission_violations': permission_violations,
                    'incidents_by_severity': incidents_by_severity
                },
                'integrity_verification': {
                    'verification_passed': integrity_check['verification_passed'],
                    'events_verified': integrity_check['events_verified'],
                    'integrity_violations': integrity_check['integrity_violations']
                }
            }
            
            logger.info(f"Generated {report_type} compliance report for {start_date} to {end_date}")
            return report
    
    def _prepare_event_data(self, event: AuthEvent) -> Dict[str, Any]:
        """Prepare event data for hashing."""
        return {
            'id': event.id,
            'event_type': event.event_type.value,
            'user_id': event.user_id,
            'username': event.username,
            'session_id': event.session_id,
            'ip_address': event.ip_address,
            'user_agent': event.user_agent,
            'resource': event.resource,
            'permission': event.permission.value if event.permission else None,
            'success': event.success,
            'error_message': event.error_message,
            'timestamp': event.timestamp.isoformat(),
            'trace_id': event.trace_id,
            'metadata': json.dumps(event.metadata, sort_keys=True) if event.metadata else None
        }
    
    def _calculate_event_hash(self, event_data: Dict[str, Any], 
                            previous_hash: Optional[str]) -> str:
        """Calculate tamper-proof hash for event."""
        # Create canonical string representation
        canonical_data = json.dumps(event_data, sort_keys=True, separators=(',', ':'))
        
        # Include previous hash in chain
        chain_data = f"{previous_hash or ''}{canonical_data}"
        
        # Calculate SHA-256 hash
        return hashlib.sha256(chain_data.encode('utf-8')).hexdigest()
    
    def _save_event_to_database(self, event: AuthEvent, event_hash: str,
                              previous_hash: Optional[str], sequence: int) -> None:
        """Save event to enhanced audit database."""
        metadata_json = json.dumps(event.metadata) if event.metadata else None
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO audit_events_enhanced (
                    id, event_type, user_id, username, session_id,
                    ip_address, user_agent, resource, permission,
                    success, error_message, timestamp, trace_id,
                    metadata, hash_chain, previous_hash, event_sequence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id, event.event_type.value, event.user_id, event.username, event.session_id,
                event.ip_address, event.user_agent, event.resource,
                event.permission.value if event.permission else None,
                event.success, event.error_message, event.timestamp.isoformat(), event.trace_id,
                metadata_json, event_hash, previous_hash, sequence
            ))
            conn.commit()
    
    def _load_last_hash(self) -> None:
        """Load the last hash from database to continue chain."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT hash_chain, event_sequence 
                FROM audit_events_enhanced 
                ORDER BY event_sequence DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                self._last_hash = row[0]
                self._event_count = row[1]
            else:
                self._last_hash = None
                self._event_count = 0
    
    def _check_security_patterns(self, event: AuthEvent) -> None:
        """Check for security patterns and create incidents if needed."""
        # This will be implemented by SecurityMonitor
        pass


class SecurityMonitor:
    """
    Security monitoring and threat detection system.
    
    Analyzes audit events in real-time to detect security threats,
    suspicious patterns, and potential attacks.
    """
    
    def __init__(self, audit_logger: AuditLogger):
        """
        Initialize security monitor.
        
        Args:
            audit_logger: Audit logger instance for event analysis.
        """
        self.audit_logger = audit_logger
        self._incident_handlers: List[Callable[[SecurityIncident], None]] = []
        
        # Pattern detection thresholds
        self.thresholds = {
            'failed_login_attempts': 5,
            'permission_violations': 10,
            'rate_limit_violations': 3,
            'concurrent_sessions': 5,
            'suspicious_ip_threshold': 20
        }
        
        logger.info("SecurityMonitor initialized")
    
    def analyze_event(self, event: AuthEvent) -> Optional[SecurityIncident]:
        """
        Analyze security event for threats.
        
        Args:
            event: Security event to analyze.
            
        Returns:
            Security incident if threat detected, None otherwise.
        """
        incidents = []
        
        # Check for brute force attacks
        if event.event_type == AuthEventType.LOGIN_FAILURE:
            incident = self._check_brute_force(event)
            if incident:
                incidents.append(incident)
        
        # Check for permission violations
        if event.event_type == AuthEventType.PERMISSION_DENIED:
            incident = self._check_permission_violations(event)
            if incident:
                incidents.append(incident)
        
        # Check for suspicious IP activity
        incident = self._check_suspicious_ip(event)
        if incident:
            incidents.append(incident)
        
        # Check for account compromise indicators
        if event.user_id:
            incident = self._check_account_compromise(event)
            if incident:
                incidents.append(incident)
        
        # Process incidents
        for incident in incidents:
            self._handle_incident(incident)
        
        return incidents[0] if incidents else None
    
    def add_incident_handler(self, handler: Callable[[SecurityIncident], None]) -> None:
        """Add incident handler callback."""
        self._incident_handlers.append(handler)
    
    def _check_brute_force(self, event: AuthEvent) -> Optional[SecurityIncident]:
        """Check for brute force login attempts."""
        # Count recent failed attempts from same IP
        recent_failures = self._count_recent_events(
            event.ip_address, AuthEventType.LOGIN_FAILURE, minutes=15
        )
        
        if recent_failures >= self.thresholds['failed_login_attempts']:
            return SecurityIncident(
                incident_type="BRUTE_FORCE_ATTACK",
                severity="HIGH",
                user_id=event.user_id,
                ip_address=event.ip_address,
                description=f"Brute force attack detected: {recent_failures} failed login attempts from {event.ip_address} in 15 minutes",
                evidence={
                    'failed_attempts': recent_failures,
                    'time_window': '15_minutes',
                    'threshold': self.thresholds['failed_login_attempts'],
                    'latest_event_id': event.id
                }
            )
        
        return None
    
    def _check_permission_violations(self, event: AuthEvent) -> Optional[SecurityIncident]:
        """Check for excessive permission violations."""
        if not event.user_id:
            return None
        
        recent_violations = self._count_recent_events(
            event.user_id, AuthEventType.PERMISSION_DENIED, minutes=60
        )
        
        if recent_violations >= self.thresholds['permission_violations']:
            return SecurityIncident(
                incident_type="PERMISSION_ESCALATION_ATTEMPT",
                severity="MEDIUM",
                user_id=event.user_id,
                ip_address=event.ip_address,
                description=f"Excessive permission violations: {recent_violations} violations by user {event.username} in 1 hour",
                evidence={
                    'violations': recent_violations,
                    'time_window': '1_hour',
                    'threshold': self.thresholds['permission_violations'],
                    'permission': event.permission.value if event.permission else None,
                    'resource': event.resource
                }
            )
        
        return None
    
    def _check_suspicious_ip(self, event: AuthEvent) -> Optional[SecurityIncident]:
        """Check for suspicious IP activity."""
        # Count total events from this IP in last hour
        recent_activity = self._count_recent_events(
            event.ip_address, None, minutes=60
        )
        
        if recent_activity >= self.thresholds['suspicious_ip_threshold']:
            return SecurityIncident(
                incident_type="SUSPICIOUS_IP_ACTIVITY",
                severity="MEDIUM",
                ip_address=event.ip_address,
                description=f"Suspicious activity from IP {event.ip_address}: {recent_activity} events in 1 hour",
                evidence={
                    'total_events': recent_activity,
                    'time_window': '1_hour',
                    'threshold': self.thresholds['suspicious_ip_threshold']
                }
            )
        
        return None
    
    def _check_account_compromise(self, event: AuthEvent) -> Optional[SecurityIncident]:
        """Check for account compromise indicators."""
        # Look for unusual patterns (this is a simplified check)
        if event.event_type == AuthEventType.LOGIN_SUCCESS:
            # Check for logins from multiple IPs in short time
            recent_ips = self._get_recent_login_ips(event.user_id, minutes=30)
            
            if len(recent_ips) > 3:  # More than 3 different IPs in 30 minutes
                return SecurityIncident(
                    incident_type="POTENTIAL_ACCOUNT_COMPROMISE",
                    severity="HIGH",
                    user_id=event.user_id,
                    ip_address=event.ip_address,
                    description=f"Potential account compromise: User {event.username} logged in from {len(recent_ips)} different IPs in 30 minutes",
                    evidence={
                        'unique_ips': list(recent_ips),
                        'time_window': '30_minutes',
                        'current_ip': event.ip_address
                    }
                )
        
        return None
    
    def _count_recent_events(self, identifier: str, event_type: Optional[AuthEventType],
                           minutes: int) -> int:
        """Count recent events for an identifier."""
        since_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        with sqlite3.connect(str(self.audit_logger.db_path)) as conn:
            if event_type:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM audit_events_enhanced
                    WHERE (user_id = ? OR ip_address = ?) 
                    AND event_type = ? 
                    AND timestamp >= ?
                """, (identifier, identifier, event_type.value, since_time.isoformat()))
            else:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM audit_events_enhanced
                    WHERE (user_id = ? OR ip_address = ?) 
                    AND timestamp >= ?
                """, (identifier, identifier, since_time.isoformat()))
            
            return cursor.fetchone()[0]
    
    def _get_recent_login_ips(self, user_id: str, minutes: int) -> Set[str]:
        """Get unique IP addresses for recent successful logins."""
        since_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        with sqlite3.connect(str(self.audit_logger.db_path)) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT ip_address FROM audit_events_enhanced
                WHERE user_id = ? 
                AND event_type = 'auth.login.success'
                AND timestamp >= ?
            """, (user_id, since_time.isoformat()))
            
            return {row[0] for row in cursor.fetchall()}
    
    def _handle_incident(self, incident: SecurityIncident) -> None:
        """Handle detected security incident."""
        # Save incident to database
        self._save_incident(incident)
        
        # Notify incident handlers
        for handler in self._incident_handlers:
            try:
                handler(incident)
            except Exception as e:
                logger.error(f"Incident handler error: {e}")
        
        logger.warning(f"Security incident detected: {incident.incident_type} - {incident.description}")
    
    def _save_incident(self, incident: SecurityIncident) -> None:
        """Save security incident to database."""
        evidence_json = json.dumps(incident.evidence)
        
        with sqlite3.connect(str(self.audit_logger.db_path)) as conn:
            conn.execute("""
                INSERT INTO security_incidents (
                    incident_id, incident_type, severity, user_id, ip_address,
                    description, evidence, detected_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.incident_id, incident.incident_type, incident.severity,
                incident.user_id, incident.ip_address, incident.description,
                evidence_json, incident.detected_at.isoformat(), incident.status
            ))
            conn.commit()


class ComplianceAuditor:
    """
    Compliance auditing and reporting system.
    
    Provides compliance reporting, audit trail verification, and
    regulatory compliance checks for security events and user activities.
    """
    
    def __init__(self, audit_logger: AuditLogger):
        """
        Initialize compliance auditor.
        
        Args:
            audit_logger: Audit logger instance for compliance analysis.
        """
        self.audit_logger = audit_logger
        
        logger.info("ComplianceAuditor initialized")
    
    def generate_sox_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate SOX compliance report."""
        return self.audit_logger.generate_compliance_report(start_date, end_date, "sox")
    
    def generate_gdpr_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate GDPR compliance report."""
        # Focus on data access and user rights
        report = self.audit_logger.generate_compliance_report(start_date, end_date, "gdpr")
        
        # Add GDPR-specific metrics
        with sqlite3.connect(str(self.audit_logger.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            
            # Data access requests
            cursor = conn.execute("""
                SELECT COUNT(*) as data_access_requests
                FROM audit_events_enhanced
                WHERE timestamp BETWEEN ? AND ?
                AND resource LIKE '%/users/%/data'
            """, (start_date.isoformat(), end_date.isoformat()))
            
            gdpr_metrics = dict(cursor.fetchone())
            report['gdpr_metrics'] = gdpr_metrics
        
        return report
    
    def verify_compliance_controls(self) -> Dict[str, Any]:
        """Verify that compliance controls are functioning."""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'controls_verified': [],
            'control_failures': [],
            'overall_status': 'PASS'
        }
        
        # Verify audit logging is working
        try:
            test_event = AuthEvent(
                event_type=AuthEventType.LOGIN_SUCCESS,
                ip_address="127.0.0.1",
                success=True,
                metadata={'compliance_test': True}
            )
            hash_result = self.audit_logger.log_security_event(test_event)
            if hash_result:
                results['controls_verified'].append('audit_logging')
            else:
                results['control_failures'].append('audit_logging')
        except Exception as e:
            results['control_failures'].append(f'audit_logging: {str(e)}')
        
        # Verify hash chain integrity
        integrity_result = self.audit_logger.verify_audit_integrity()
        if integrity_result['verification_passed']:
            results['controls_verified'].append('hash_chain_integrity')
        else:
            results['control_failures'].append('hash_chain_integrity')
        
        if results['control_failures']:
            results['overall_status'] = 'FAIL'
        
        return results


# Enhanced integration with security manager
def integrate_audit_system():
    """Integrate enhanced audit system with security manager."""
    audit_logger = AuditLogger()
    security_monitor = SecurityMonitor(audit_logger)
    compliance_auditor = ComplianceAuditor(audit_logger)
    
    # Override security manager's audit logging
    security_manager = get_security_manager()
    original_log_method = security_manager._log_audit_event
    
    def enhanced_log_audit_event(event: AuthEvent) -> None:
        # Log to enhanced audit system
        audit_logger.log_security_event(event)
        
        # Analyze for security threats
        security_monitor.analyze_event(event)
        
        # Keep original functionality
        original_log_method(event)
    
    security_manager._log_audit_event = enhanced_log_audit_event
    
    return audit_logger, security_monitor, compliance_auditor


# Global instances
_audit_logger: Optional[AuditLogger] = None
_security_monitor: Optional[SecurityMonitor] = None
_compliance_auditor: Optional[ComplianceAuditor] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_security_monitor() -> SecurityMonitor:
    """Get global security monitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor(get_audit_logger())
    return _security_monitor


def get_compliance_auditor() -> ComplianceAuditor:
    """Get global compliance auditor instance."""
    global _compliance_auditor
    if _compliance_auditor is None:
        _compliance_auditor = ComplianceAuditor(get_audit_logger())
    return _compliance_auditor