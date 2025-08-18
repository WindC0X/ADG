"""
Unit tests for the node engine core functionality.

Tests the ProcessingNode base class, data models, and core interfaces.
"""

import pytest
import tempfile
import json
from datetime import datetime
from pathlib import Path

from core.node_interfaces import (
    ProcessingNode, NodeInput, NodeOutput, ValidationResult,
    ValidationSeverity, NodeStatus, ArchiveDocument, 
    DirectoryConfig, WorkflowContext
)


class MockProcessingNode(ProcessingNode):
    """Mock node implementation for testing."""
    
    def validate_input(self, input_data):
        return [ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message="Mock validation passed"
        )]
    
    def process(self, input_data):
        return self._create_output({"result": "mock_processed"})
    
    def get_schema(self):
        return {
            "node_type": "MockNode",
            "description": "Mock node for testing"
        }


class TestNodeInterfaces:
    """Test core node interfaces and data models."""
    
    def test_node_input_creation(self):
        """Test NodeInput creation and methods."""
        data = {"key1": "value1", "key2": 42}
        metadata = {"source": "test"}
        
        node_input = NodeInput(
            data=data,
            metadata=metadata,
            node_id="test_node"
        )
        
        assert node_input.data == data
        assert node_input.metadata == metadata
        assert node_input.node_id == "test_node"
        assert isinstance(node_input.timestamp, datetime)
        
        # Test methods
        assert node_input.get_value("key1") == "value1"
        assert node_input.get_value("nonexistent", "default") == "default"
        assert node_input.has_key("key1") is True
        assert node_input.has_key("nonexistent") is False
    
    def test_node_output_creation(self):
        """Test NodeOutput creation and methods."""
        data = {"result": "success"}
        
        node_output = NodeOutput(
            data=data,
            node_id="test_node",
            status=NodeStatus.COMPLETED
        )
        
        assert node_output.data == data
        assert node_output.node_id == "test_node"
        assert node_output.status == NodeStatus.COMPLETED
        assert isinstance(node_output.timestamp, datetime)
        assert node_output.errors == []
        assert node_output.warnings == []
        
        # Test methods
        node_output.add_error("Test error")
        assert "Test error" in node_output.errors
        assert node_output.status == NodeStatus.FAILED
        
        node_output.add_warning("Test warning")
        assert "Test warning" in node_output.warnings
        
        node_output.set_value("new_key", "new_value")
        assert node_output.data["new_key"] == "new_value"
    
    def test_archive_document_creation(self):
        """Test ArchiveDocument data model."""
        doc = ArchiveDocument(
            id="doc_001",
            title="Test Document",
            file_path="/path/to/file.pdf"
        )
        
        assert doc.id == "doc_001"
        assert doc.title == "Test Document"
        assert doc.file_path == "/path/to/file.pdf"
        assert isinstance(doc.created_at, datetime)
        assert doc.tags == []
        assert doc.metadata == {}
        
        # Test methods
        doc.add_tag("important")
        assert "important" in doc.tags
        
        doc.add_tag("important")  # Should not duplicate
        assert doc.tags.count("important") == 1
        
        doc.set_metadata("category", "financial")
        assert doc.metadata["category"] == "financial"
    
    def test_directory_config_creation(self):
        """Test DirectoryConfig data model."""
        config = DirectoryConfig(
            template_path="/templates/template.xlsx",
            output_path="/output",
            directory_type="卷内目录"
        )
        
        assert config.template_path == "/templates/template.xlsx"
        assert config.output_path == "/output"
        assert config.directory_type == "卷内目录"
        assert config.column_mappings == {}
        assert config.page_settings == {}
        assert config.height_calculation_method == "pillow"
    
    def test_workflow_context_creation(self):
        """Test WorkflowContext data model."""
        context = WorkflowContext(
            workflow_id="workflow_001",
            status=NodeStatus.PENDING
        )
        
        assert context.workflow_id == "workflow_001"
        assert context.status == NodeStatus.PENDING
        assert isinstance(context.started_at, datetime)
        assert context.completed_at is None
        assert context.execution_state == {}
        assert context.shared_data == {}
        
        # Test methods
        context.set_shared_data("key", "value")
        assert context.get_shared_data("key") == "value"
        assert context.get_shared_data("nonexistent", "default") == "default"
        
        context.update_execution_state("node1", {"status": "running"})
        assert context.execution_state["node1"]["status"] == "running"
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            is_valid=False,
            severity=ValidationSeverity.ERROR,
            message="Test error message",
            field_name="test_field",
            error_code="TEST_ERROR"
        )
        
        assert result.is_valid is False
        assert result.severity == ValidationSeverity.ERROR
        assert result.message == "Test error message"
        assert result.field_name == "test_field"
        assert result.error_code == "TEST_ERROR"


class TestProcessingNodeBase:
    """Test ProcessingNode base class functionality."""
    
    def test_node_creation(self):
        """Test basic node creation."""
        config = {"param1": "value1"}
        node = MockProcessingNode("test_node", config)
        
        assert node.node_id == "test_node"
        assert node.config == config
        assert node.get_memory_usage() == 0.0
    
    def test_node_validation(self):
        """Test node input validation."""
        node = MockProcessingNode("test_node")
        input_data = NodeInput(data={"test": "data"})
        
        results = node.validate_input(input_data)
        assert len(results) > 0
        assert results[0].is_valid is True
        assert results[0].severity == ValidationSeverity.INFO
    
    def test_node_processing(self):
        """Test node processing."""
        node = MockProcessingNode("test_node")
        input_data = NodeInput(data={"test": "data"})
        
        output = node.process(input_data)
        
        assert isinstance(output, NodeOutput)
        assert output.node_id == "test_node"
        assert output.status == NodeStatus.COMPLETED
        assert output.data["result"] == "mock_processed"
        assert "node_type" in output.metadata
    
    def test_node_schema(self):
        """Test node schema retrieval."""
        node = MockProcessingNode("test_node")
        schema = node.get_schema()
        
        assert schema["node_type"] == "MockNode"
        assert "description" in schema
    
    def test_memory_tracking(self):
        """Test memory usage tracking."""
        node = MockProcessingNode("test_node")
        
        # Test memory update
        node._update_memory_usage(25.5)
        assert node.get_memory_usage() == 25.5
    
    def test_helper_methods(self):
        """Test helper methods."""
        node = MockProcessingNode("test_node")
        
        # Test create output helper
        output = node._create_output({"test": "data"}, 123.45)
        assert output.data["test"] == "data"
        assert output.processing_time_ms == 123.45
        assert output.node_id == "test_node"
        
        # Test validate required fields helper
        input_data = NodeInput(data={"field1": "value1"})
        results = node._validate_required_fields(input_data, ["field1", "field2"])
        
        # Should have one error for missing field2
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert len(error_results) == 1
        assert "field2" in error_results[0].message


if __name__ == "__main__":
    pytest.main([__file__])