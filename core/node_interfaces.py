"""
Node interfaces and data models for the ADG platform.

This module defines the core interfaces and data structures for the node-based
execution engine, providing standardized contracts for all processing nodes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum, auto
import logging

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Status enumeration for node execution."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class ValidationSeverity(Enum):
    """Severity levels for validation results."""

    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class ValidationResult:
    """Result of input validation."""

    is_valid: bool
    severity: ValidationSeverity
    message: str
    field_name: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class NodeInput:
    """Standard input data model for all nodes."""

    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    node_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the data dictionary with optional default."""
        return self.data.get(key, default)

    def has_key(self, key: str) -> bool:
        """Check if a key exists in the data."""
        return key in self.data


@dataclass
class NodeOutput:
    """Standard output data model for all nodes."""

    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    node_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: NodeStatus = NodeStatus.COMPLETED
    processing_time_ms: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message to the output."""
        self.errors.append(error)
        if self.status == NodeStatus.COMPLETED:
            self.status = NodeStatus.FAILED

    def add_warning(self, warning: str) -> None:
        """Add a warning message to the output."""
        self.warnings.append(warning)

    def set_value(self, key: str, value: Any) -> None:
        """Set a value in the output data."""
        self.data[key] = value


@dataclass
class ArchiveDocument:
    """Data model for an archive document."""

    id: str
    title: str
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    content: Optional[str] = None

    def add_tag(self, tag: str) -> None:
        """Add a tag to the document."""
        if tag not in self.tags:
            self.tags.append(tag)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for the document."""
        self.metadata[key] = value


@dataclass
class DirectoryConfig:
    """Configuration model for directory generation workflows."""

    template_path: str
    output_path: str
    directory_type: str
    column_mappings: Dict[str, str] = field(default_factory=dict)
    page_settings: Dict[str, Any] = field(default_factory=dict)
    height_calculation_method: str = "pillow"
    auto_fit_columns: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    """Execution state container for DAG processing."""

    workflow_id: str
    current_node_id: Optional[str] = None
    execution_state: Dict[str, Any] = field(default_factory=dict)
    shared_data: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: NodeStatus = NodeStatus.PENDING

    def set_shared_data(self, key: str, value: Any) -> None:
        """Set shared data that can be accessed by all nodes."""
        self.shared_data[key] = value

    def get_shared_data(self, key: str, default: Any = None) -> Any:
        """Get shared data value."""
        return self.shared_data.get(key, default)

    def update_execution_state(self, node_id: str, state: Dict[str, Any]) -> None:
        """Update the execution state for a specific node."""
        self.execution_state[node_id] = state


class ProcessingNode(ABC):
    """
    Abstract base class for all processing nodes.

    This class defines the standard interface that all processing nodes must implement,
    ensuring consistency across the node execution engine.
    """

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the processing node.

        Args:
            node_id: Unique identifier for this node instance.
            config: Optional configuration dictionary for the node.
        """
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self._memory_usage_mb = 0.0

    @abstractmethod
    def validate_input(self, input_data: NodeInput) -> List[ValidationResult]:
        """
        Validate input data before processing.

        Args:
            input_data: The input data to validate.

        Returns:
            List of validation results indicating any issues found.
        """
        pass

    @abstractmethod
    def process(self, input_data: NodeInput) -> NodeOutput:
        """
        Process the input data and return the result.

        Args:
            input_data: The input data to process.

        Returns:
            The processing result wrapped in a NodeOutput object.
        """
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's configuration and input/output.

        Returns:
            A dictionary containing the JSON schema definition.
        """
        pass

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self._memory_usage_mb

    def _update_memory_usage(self, usage_mb: float) -> None:
        """Update the current memory usage tracking."""
        self._memory_usage_mb = usage_mb

        # Log warning if approaching memory budget
        if usage_mb > 40.0:  # 80% of 50MB budget
            self.logger.warning(
                f"Node {self.node_id} memory usage approaching budget: {usage_mb:.1f}MB"
            )

    def _create_output(
        self, data: Dict[str, Any], processing_time_ms: Optional[float] = None
    ) -> NodeOutput:
        """
        Helper method to create a standardized NodeOutput.

        Args:
            data: The output data.
            processing_time_ms: Optional processing time in milliseconds.

        Returns:
            A properly formatted NodeOutput object.
        """
        return NodeOutput(
            data=data,
            node_id=self.node_id,
            processing_time_ms=processing_time_ms,
            metadata={"node_type": self.__class__.__name__},
        )

    def _validate_required_fields(
        self, input_data: NodeInput, required_fields: List[str]
    ) -> List[ValidationResult]:
        """
        Helper method to validate required fields in input data.

        Args:
            input_data: The input data to validate.
            required_fields: List of required field names.

        Returns:
            List of validation results for missing fields.
        """
        results = []
        for field in required_fields:
            if not input_data.has_key(field):
                results.append(
                    ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Required field '{field}' is missing",
                        field_name=field,
                        error_code="MISSING_REQUIRED_FIELD",
                    )
                )
        return results


# Type aliases for better code readability
ProcessingResult = Dict[str, Union[bool, str, float, List[str]]]
DocumentId = str
MetadataDict = Dict[str, Any]
ConfigDict = Dict[str, Any]
