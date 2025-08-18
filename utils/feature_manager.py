"""
Feature flag management system for progressive migration.

This module provides a robust feature flag system that allows safe transition
between legacy and new system implementations with shadow-write validation
and rollback capabilities.
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, TypeVar, Union
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class FeatureFlagStatus(Enum):
    """Status of a feature flag."""
    DISABLED = auto()
    ENABLED = auto()
    SHADOW = auto()  # Shadow mode - run both implementations
    ROLLBACK = auto()  # Rollback mode - use legacy only


class ValidationMode(Enum):
    """Mode for shadow-write validation."""
    STRICT = auto()      # Results must match exactly
    TOLERANT = auto()    # Minor differences allowed
    LOGGING_ONLY = auto() # Log differences but don't fail


@dataclass
class FeatureFlagConfig:
    """Configuration for a single feature flag."""
    name: str
    status: FeatureFlagStatus
    description: str
    rollout_percentage: float = 0.0  # 0-100, gradual rollout
    validation_mode: ValidationMode = ValidationMode.STRICT
    enabled_for_users: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


@dataclass
class ShadowWriteResult:
    """Result of a shadow-write validation."""
    feature_name: str
    legacy_result: Any
    new_result: Any
    matches: bool
    differences: List[str]
    execution_time_legacy_ms: float
    execution_time_new_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class FeatureFlagManager:
    """
    Manages feature flags for progressive system migration.
    
    Supports gradual rollout, shadow-write validation, and safe rollback
    capabilities for transitioning between legacy and new implementations.
    """
    
    def __init__(self, config_path: str = "config/feature_flags.json"):
        """
        Initialize the feature flag manager.
        
        Args:
            config_path: Path to the feature flags configuration file.
        """
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._flags: Dict[str, FeatureFlagConfig] = {}
        self._lock = threading.RLock()
        self._shadow_results: List[ShadowWriteResult] = []
        self._validation_callbacks: Dict[str, Callable] = {}
        
        self._load_configuration()
    
    def create_flag(self, name: str, description: str, 
                   status: FeatureFlagStatus = FeatureFlagStatus.DISABLED,
                   rollout_percentage: float = 0.0,
                   validation_mode: ValidationMode = ValidationMode.STRICT,
                   expires_in_days: Optional[int] = None) -> None:
        """
        Create a new feature flag.
        
        Args:
            name: Unique name for the feature flag.
            description: Human-readable description.
            status: Initial status of the flag.
            rollout_percentage: Percentage of users to enable for (0-100).
            validation_mode: Mode for shadow-write validation.
            expires_in_days: Optional expiration in days.
        """
        with self._lock:
            if name in self._flags:
                raise ValueError(f"Feature flag '{name}' already exists")
            
            expires_at = None
            if expires_in_days is not None:
                expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            flag = FeatureFlagConfig(
                name=name,
                status=status,
                description=description,
                rollout_percentage=rollout_percentage,
                validation_mode=validation_mode,
                expires_at=expires_at
            )
            
            self._flags[name] = flag
            self._save_configuration()
            
            logger.info(f"Created feature flag '{name}' with status {status.name}")
    
    def update_flag(self, name: str, **kwargs) -> None:
        """
        Update an existing feature flag.
        
        Args:
            name: Name of the feature flag to update.
            **kwargs: Field values to update.
        """
        with self._lock:
            if name not in self._flags:
                raise ValueError(f"Feature flag '{name}' does not exist")
            
            flag = self._flags[name]
            old_status = flag.status
            
            # Update allowed fields
            for field_name, value in kwargs.items():
                if hasattr(flag, field_name):
                    setattr(flag, field_name, value)
            
            flag.updated_at = datetime.utcnow()
            self._save_configuration()
            
            logger.info(f"Updated feature flag '{name}': {old_status.name} -> {flag.status.name}")
    
    def is_enabled(self, name: str, user_id: Optional[str] = None, 
                  context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if a feature flag is enabled for the given context.
        
        Args:
            name: Name of the feature flag.
            user_id: Optional user ID for user-specific enablement.
            context: Optional context for evaluation.
            
        Returns:
            True if the feature is enabled, False otherwise.
        """
        with self._lock:
            flag = self._flags.get(name)
            if not flag:
                logger.warning(f"Feature flag '{name}' not found, defaulting to disabled")
                return False
            
            # Check expiration
            if flag.expires_at and datetime.utcnow() > flag.expires_at:
                logger.warning(f"Feature flag '{name}' has expired")
                return False
            
            # Handle different statuses
            if flag.status == FeatureFlagStatus.DISABLED:
                return False
            elif flag.status == FeatureFlagStatus.ENABLED:
                return True
            elif flag.status == FeatureFlagStatus.ROLLBACK:
                return False
            elif flag.status == FeatureFlagStatus.SHADOW:
                # In shadow mode, consider it "enabled" for shadow execution
                return True
            
            # Check user-specific enablement
            if user_id and user_id in flag.enabled_for_users:
                return True
            
            # Check rollout percentage
            if flag.rollout_percentage > 0:
                # Simple hash-based rollout (deterministic per user)
                if user_id:
                    user_hash = hash(f"{name}:{user_id}") % 100
                    return user_hash < flag.rollout_percentage
                else:
                    # Random rollout if no user ID
                    import random
                    return random.random() * 100 < flag.rollout_percentage
            
            return False
    
    def should_use_shadow_mode(self, name: str) -> bool:
        """Check if a feature should run in shadow mode."""
        with self._lock:
            flag = self._flags.get(name)
            return flag and flag.status == FeatureFlagStatus.SHADOW
    
    def should_rollback(self, name: str) -> bool:
        """Check if a feature should use rollback (legacy only)."""
        with self._lock:
            flag = self._flags.get(name)
            return flag and flag.status == FeatureFlagStatus.ROLLBACK
    
    @contextmanager
    def shadow_execution(self, feature_name: str, legacy_func: Callable[[], T], 
                        new_func: Callable[[], T], *args, **kwargs):
        """
        Execute both legacy and new implementations with validation.
        
        Args:
            feature_name: Name of the feature flag.
            legacy_func: Legacy implementation function.
            new_func: New implementation function.
            
        Yields:
            The result from the appropriate implementation.
        """
        flag = self._flags.get(feature_name)
        if not flag:
            # No flag exists, use legacy
            yield legacy_func(*args, **kwargs)
            return
        
        if flag.status == FeatureFlagStatus.ROLLBACK:
            # Rollback mode - use legacy only
            yield legacy_func(*args, **kwargs)
            return
        
        if flag.status == FeatureFlagStatus.ENABLED:
            # New implementation only
            yield new_func(*args, **kwargs)
            return
        
        if flag.status == FeatureFlagStatus.SHADOW:
            # Shadow mode - run both and validate
            import time
            
            # Execute legacy implementation
            start_time = time.perf_counter()
            try:
                legacy_result = legacy_func(*args, **kwargs)
                legacy_time_ms = (time.perf_counter() - start_time) * 1000
                legacy_error = None
            except Exception as e:
                legacy_result = None
                legacy_time_ms = (time.perf_counter() - start_time) * 1000
                legacy_error = str(e)
            
            # Execute new implementation
            start_time = time.perf_counter()
            try:
                new_result = new_func(*args, **kwargs)
                new_time_ms = (time.perf_counter() - start_time) * 1000
                new_error = None
            except Exception as e:
                new_result = None
                new_time_ms = (time.perf_counter() - start_time) * 1000
                new_error = str(e)
            
            # Validate results
            validation_result = self._validate_shadow_results(
                feature_name, legacy_result, new_result, 
                legacy_time_ms, new_time_ms, legacy_error, new_error
            )
            
            self._shadow_results.append(validation_result)
            
            # Return the appropriate result based on validation
            if flag.validation_mode == ValidationMode.STRICT and not validation_result.matches:
                logger.warning(f"Shadow validation failed for '{feature_name}', using legacy result")
                if legacy_error:
                    raise Exception(legacy_error)
                yield legacy_result
            else:
                # Use new result if available, fallback to legacy
                if new_error:
                    if legacy_error:
                        raise Exception(f"Both implementations failed: legacy={legacy_error}, new={new_error}")
                    logger.warning(f"New implementation failed for '{feature_name}', using legacy result")
                    yield legacy_result
                else:
                    yield new_result
        else:
            # Disabled - use legacy
            yield legacy_func(*args, **kwargs)
    
    def get_shadow_results(self, feature_name: Optional[str] = None, 
                          limit: int = 100) -> List[ShadowWriteResult]:
        """Get shadow-write validation results."""
        with self._lock:
            if feature_name:
                results = [r for r in self._shadow_results if r.feature_name == feature_name]
            else:
                results = self._shadow_results.copy()
            
            # Return most recent results
            return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def clear_shadow_results(self, feature_name: Optional[str] = None) -> None:
        """Clear shadow-write validation results."""
        with self._lock:
            if feature_name:
                self._shadow_results = [r for r in self._shadow_results if r.feature_name != feature_name]
            else:
                self._shadow_results.clear()
    
    def get_flag_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status information for a feature flag."""
        with self._lock:
            flag = self._flags.get(name)
            if not flag:
                return None
            
            # Get recent shadow results
            shadow_results = self.get_shadow_results(name, limit=10)
            
            return {
                "name": flag.name,
                "status": flag.status.name,
                "description": flag.description,
                "rollout_percentage": flag.rollout_percentage,
                "validation_mode": flag.validation_mode.name,
                "enabled_for_users": flag.enabled_for_users,
                "created_at": flag.created_at.isoformat(),
                "updated_at": flag.updated_at.isoformat(),
                "expires_at": flag.expires_at.isoformat() if flag.expires_at else None,
                "metadata": flag.metadata,
                "recent_shadow_results": len(shadow_results),
                "shadow_success_rate": self._calculate_success_rate(shadow_results)
            }
    
    def list_flags(self) -> List[Dict[str, Any]]:
        """List all feature flags with their status."""
        with self._lock:
            return [self.get_flag_status(name) for name in self._flags.keys()]
    
    def rollback_flag(self, name: str, reason: str) -> None:
        """
        Rollback a feature flag to legacy implementation.
        
        Args:
            name: Name of the feature flag to rollback.
            reason: Reason for the rollback.
        """
        with self._lock:
            if name not in self._flags:
                raise ValueError(f"Feature flag '{name}' does not exist")
            
            flag = self._flags[name]
            old_status = flag.status
            
            flag.status = FeatureFlagStatus.ROLLBACK
            flag.updated_at = datetime.utcnow()
            flag.metadata["rollback_reason"] = reason
            flag.metadata["rollback_at"] = datetime.utcnow().isoformat()
            flag.metadata["rollback_from"] = old_status.name
            
            self._save_configuration()
            
            logger.warning(f"Rolled back feature flag '{name}': {reason}")
    
    def _validate_shadow_results(self, feature_name: str, legacy_result: Any, 
                                new_result: Any, legacy_time_ms: float, 
                                new_time_ms: float, legacy_error: Optional[str],
                                new_error: Optional[str]) -> ShadowWriteResult:
        """Validate results from shadow execution."""
        differences = []
        matches = True
        
        # Compare errors
        if legacy_error != new_error:
            differences.append(f"Error mismatch: legacy={legacy_error}, new={new_error}")
            matches = False
        
        # Compare results if no errors
        if not legacy_error and not new_error:
            if legacy_result != new_result:
                # Try to provide more detailed comparison
                if hasattr(legacy_result, '__dict__') and hasattr(new_result, '__dict__'):
                    # Compare object attributes
                    legacy_dict = vars(legacy_result)
                    new_dict = vars(new_result)
                    
                    for key in set(legacy_dict.keys()) | set(new_dict.keys()):
                        if legacy_dict.get(key) != new_dict.get(key):
                            differences.append(f"Attribute '{key}': legacy={legacy_dict.get(key)}, new={new_dict.get(key)}")
                else:
                    differences.append(f"Result mismatch: legacy={legacy_result}, new={new_result}")
                
                matches = False
        
        # Performance comparison
        performance_diff = abs(new_time_ms - legacy_time_ms)
        if performance_diff > legacy_time_ms * 0.5:  # More than 50% difference
            differences.append(f"Performance difference: legacy={legacy_time_ms:.1f}ms, new={new_time_ms:.1f}ms")
        
        return ShadowWriteResult(
            feature_name=feature_name,
            legacy_result=legacy_result,
            new_result=new_result,
            matches=matches,
            differences=differences,
            execution_time_legacy_ms=legacy_time_ms,
            execution_time_new_ms=new_time_ms
        )
    
    def _calculate_success_rate(self, results: List[ShadowWriteResult]) -> float:
        """Calculate success rate for shadow results."""
        if not results:
            return 0.0
        
        successful = sum(1 for r in results if r.matches)
        return (successful / len(results)) * 100
    
    def _load_configuration(self) -> None:
        """Load feature flags from configuration file."""
        if not self.config_path.exists():
            logger.info(f"Feature flags config file not found at {self.config_path}, starting with empty configuration")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._flags = {}
            for flag_data in data.get('flags', []):
                flag = FeatureFlagConfig(
                    name=flag_data['name'],
                    status=FeatureFlagStatus[flag_data['status']],
                    description=flag_data['description'],
                    rollout_percentage=flag_data.get('rollout_percentage', 0.0),
                    validation_mode=ValidationMode[flag_data.get('validation_mode', 'STRICT')],
                    enabled_for_users=flag_data.get('enabled_for_users', []),
                    metadata=flag_data.get('metadata', {}),
                    created_at=datetime.fromisoformat(flag_data['created_at']),
                    updated_at=datetime.fromisoformat(flag_data['updated_at']),
                    expires_at=datetime.fromisoformat(flag_data['expires_at']) if flag_data.get('expires_at') else None
                )
                self._flags[flag.name] = flag
            
            logger.info(f"Loaded {len(self._flags)} feature flags from configuration")
            
        except Exception as e:
            logger.error(f"Failed to load feature flags configuration: {e}")
            self._flags = {}
    
    def _save_configuration(self) -> None:
        """Save feature flags to configuration file."""
        try:
            data = {
                'flags': [asdict(flag) for flag in self._flags.values()],
                'last_updated': datetime.utcnow().isoformat()
            }
            
            # Convert datetime objects to strings for JSON serialization
            for flag_data in data['flags']:
                flag_data['status'] = flag_data['status'].name
                flag_data['validation_mode'] = flag_data['validation_mode'].name
                flag_data['created_at'] = flag_data['created_at'].isoformat()
                flag_data['updated_at'] = flag_data['updated_at'].isoformat()
                if flag_data['expires_at']:
                    flag_data['expires_at'] = flag_data['expires_at'].isoformat()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved feature flags configuration to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save feature flags configuration: {e}")


# Global feature flag manager instance
_feature_manager: Optional[FeatureFlagManager] = None


def get_feature_manager() -> FeatureFlagManager:
    """Get the global feature flag manager instance."""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureFlagManager()
    return _feature_manager


def is_feature_enabled(name: str, user_id: Optional[str] = None, 
                      context: Optional[Dict[str, Any]] = None) -> bool:
    """Convenience function to check if a feature is enabled."""
    return get_feature_manager().is_enabled(name, user_id, context)