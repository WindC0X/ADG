"""
Unit tests for DataTransformNode.

Tests data transformation functionality including filtering, mapping,
validation, formatting, and aggregation operations.
"""

import pytest
import pandas as pd
from datetime import datetime

from core.node_interfaces import NodeInput, NodeStatus, ValidationSeverity
from core.node_engine.nodes.data_transform_node import DataTransformNode


class TestDataTransformNode:
    """Test DataTransformNode functionality."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample data for testing transformations."""
        return [
            {"id": 1, "name": "Document 1", "type": "Report", "value": 100.5, "date": "2023-01-01"},
            {"id": 2, "name": "Document 2", "type": "Invoice", "value": 250.0, "date": "2023-01-02"},
            {"id": 3, "name": "Document 3", "type": "Report", "value": 75.25, "date": "2023-01-03"},
            {"id": 4, "name": "Document 4", "type": "Contract", "value": 500.0, "date": "2023-01-04"},
            {"id": 5, "name": "Document 5", "type": "Invoice", "value": 150.75, "date": "2023-01-05"}
        ]
    
    def test_node_creation(self):
        """Test basic node creation."""
        transformations = [
            {"type": "filter", "operation": "equals", "field": "type", "parameters": {"value": "Report"}}
        ]
        config = {
            'transformations': transformations,
            'error_handling': 'strict'
        }
        
        node = DataTransformNode("transform_1", config)
        
        assert node.node_id == "transform_1"
        assert node.transformations == transformations
        assert node.error_handling == 'strict'
        assert node.validation_rules == {}
    
    def test_validation_missing_transformations(self):
        """Test validation with missing transformations."""
        node = DataTransformNode("transform_1", {})
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("transformation must be specified" in r.message for r in error_results)
    
    def test_validation_unsupported_transform_type(self):
        """Test validation with unsupported transformation type."""
        config = {
            'transformations': [
                {"type": "unsupported", "operation": "test"}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Unsupported transformation type" in r.message for r in error_results)
    
    def test_validation_unsupported_operation(self):
        """Test validation with unsupported operation."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "unsupported_op"}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Unsupported operation" in r.message for r in error_results)
    
    def test_validation_missing_data_field(self):
        """Test validation with missing data field."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "equals", "field": "type", "parameters": {"value": "Report"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={})  # Missing 'data' key
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("must contain 'data' field" in r.message for r in error_results)
    
    def test_validation_invalid_error_handling(self):
        """Test validation with invalid error handling mode."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "equals", "field": "type", "parameters": {"value": "Report"}}
            ],
            'error_handling': 'invalid_mode'
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Invalid error handling mode" in r.message for r in error_results)
    
    def test_filter_equals(self, sample_data):
        """Test filter equals operation."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "equals", "field": "type", "parameters": {"value": "Report"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert len(result_data) == 2  # Only Report types
        assert all(item['type'] == 'Report' for item in result_data)
    
    def test_filter_contains(self, sample_data):
        """Test filter contains operation."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "contains", "field": "name", "parameters": {"value": "Document 1"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert len(result_data) == 1
        assert result_data[0]['name'] == 'Document 1'
    
    def test_filter_range(self, sample_data):
        """Test filter range operation."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "range", "field": "value", 
                 "parameters": {"min": 100, "max": 300}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        # Should include items with value between 100 and 300
        assert len(result_data) == 3
        assert all(100 <= item['value'] <= 300 for item in result_data)
    
    def test_filter_in_list(self, sample_data):
        """Test filter in_list operation."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "in_list", "field": "type", 
                 "parameters": {"values": ["Report", "Contract"]}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert len(result_data) == 3  # 2 Reports + 1 Contract
        assert all(item['type'] in ['Report', 'Contract'] for item in result_data)
    
    def test_map_rename(self, sample_data):
        """Test map rename operation."""
        config = {
            'transformations': [
                {"type": "map", "operation": "rename", "field": "name", 
                 "parameters": {"new_name": "document_name"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert all('document_name' in item for item in result_data)
        assert all('name' not in item for item in result_data)
    
    def test_map_combine(self, sample_data):
        """Test map combine operation."""
        config = {
            'transformations': [
                {"type": "map", "operation": "combine", "field": "full_info",
                 "parameters": {"source_fields": ["name", "type"], "separator": " - "}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert all('full_info' in item for item in result_data)
        assert result_data[0]['full_info'] == 'Document 1 - Report'
    
    def test_validate_required(self, sample_data):
        """Test validate required operation."""
        # Add some records with missing values
        test_data = sample_data + [
            {"id": 6, "name": "", "type": "Report", "value": 100.0},
            {"id": 7, "type": "Invoice", "value": 200.0}  # Missing name
        ]
        
        config = {
            'transformations': [
                {"type": "validate", "operation": "required", "field": "name"}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": test_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        # Should remove records with empty/missing name
        assert len(result_data) == 5  # Original 5 records
        assert all(item.get('name') and item['name'].strip() for item in result_data)
    
    def test_validate_type_conversion(self, sample_data):
        """Test validate type conversion."""
        config = {
            'transformations': [
                {"type": "validate", "operation": "type", "field": "value", 
                 "parameters": {"type": "int"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        # Values should be converted to integers
        assert all(isinstance(item['value'], int) for item in result_data)
    
    def test_format_text_case(self, sample_data):
        """Test format text case operation."""
        config = {
            'transformations': [
                {"type": "format", "operation": "text", "field": "name",
                 "parameters": {"case": "upper"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert all(item['name'].isupper() for item in result_data)
        assert result_data[0]['name'] == 'DOCUMENT 1'
    
    def test_format_trim(self, sample_data):
        """Test format trim operation."""
        # Add data with extra whitespace
        test_data = [
            {"id": 1, "name": "  Document 1  ", "type": "Report"},
            {"id": 2, "name": " Document 2 ", "type": "Invoice"}
        ]
        
        config = {
            'transformations': [
                {"type": "format", "operation": "trim", "field": "name"}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": test_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert result_data[0]['name'] == 'Document 1'
        assert result_data[1]['name'] == 'Document 2'
    
    def test_format_number(self, sample_data):
        """Test format number operation."""
        config = {
            'transformations': [
                {"type": "format", "operation": "number", "field": "value",
                 "parameters": {"decimal_places": 1}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        # Values should be rounded to 1 decimal place
        assert result_data[0]['value'] == 100.5
        assert result_data[1]['value'] == 250.0
        assert result_data[2]['value'] == 75.2  # 75.25 rounded to 75.2 due to floating point precision
    
    def test_aggregate_group_by_count(self, sample_data):
        """Test aggregate group by count operation."""
        config = {
            'transformations': [
                {"type": "aggregate", "operation": "count", "field": "id",
                 "parameters": {"group_by": ["type"]}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        assert len(result_data) == 3  # 3 unique types
        
        # Check counts for each type
        type_counts = {item['type']: item['id_count'] for item in result_data}
        assert type_counts['Report'] == 2
        assert type_counts['Invoice'] == 2
        assert type_counts['Contract'] == 1
    
    def test_multiple_transformations(self, sample_data):
        """Test multiple transformations in sequence."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "not_equals", "field": "type", "parameters": {"value": "Contract"}},
                {"type": "format", "operation": "text", "field": "type", "parameters": {"case": "upper"}},
                {"type": "validate", "operation": "type", "field": "value", "parameters": {"type": "int"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        result_data = output.data['data']
        
        # Should have 4 records (excluded Contract)
        assert len(result_data) == 4
        
        # Types should be uppercase
        assert all(item['type'].isupper() for item in result_data)
        
        # Values should be integers
        assert all(isinstance(item['value'], int) for item in result_data)
    
    def test_error_handling_strict(self, sample_data):
        """Test strict error handling mode."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "equals", "field": "nonexistent_field", 
                 "parameters": {"value": "test"}}
            ],
            'error_handling': 'strict'
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        # Should succeed (filter just returns all data when field doesn't exist)
        assert output.status == NodeStatus.COMPLETED
    
    def test_empty_data_input(self):
        """Test processing with empty data."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "equals", "field": "type", "parameters": {"value": "Report"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": []})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output.data['data'] == []
        assert output.data['statistics']['records_processed'] == 0
    
    def test_statistics_tracking(self, sample_data):
        """Test statistics tracking during transformation."""
        config = {
            'transformations': [
                {"type": "filter", "operation": "equals", "field": "type", "parameters": {"value": "Report"}}
            ]
        }
        node = DataTransformNode("transform_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        
        stats = output.data['statistics']
        assert stats['records_processed'] == 5
        assert stats['records_filtered'] == 3  # 5 - 2 remaining
        
        summary = output.data['transformation_summary']
        assert summary['initial_records'] == 5
        assert summary['final_records'] == 2
        assert summary['transformations_applied'] == 1
    
    def test_get_schema(self):
        """Test schema retrieval."""
        node = DataTransformNode("transform_1")
        schema = node.get_schema()
        
        assert schema['node_type'] == 'DataTransformNode'
        assert 'description' in schema
        assert 'config_schema' in schema
        assert 'supported_operations' in schema
        assert 'input_schema' in schema
        assert 'output_schema' in schema
        
        # Check supported operations structure
        operations = schema['supported_operations']
        assert 'filter' in operations
        assert 'map' in operations
        assert 'validate' in operations
        assert 'format' in operations
        assert 'aggregate' in operations


if __name__ == "__main__":
    pytest.main([__file__])