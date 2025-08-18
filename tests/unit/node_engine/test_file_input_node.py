"""
Unit tests for FileInputNode.

Tests file reading functionality for Excel, CSV, and JSON formats
with comprehensive error handling.
"""

import pytest
import tempfile
import json
import pandas as pd
from pathlib import Path

from core.node_interfaces import NodeInput, NodeStatus, ValidationSeverity
from core.node_engine.nodes.file_input_node import FileInputNode


class TestFileInputNode:
    """Test FileInputNode functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return [
            {"id": 1, "name": "Document 1", "type": "Report"},
            {"id": 2, "name": "Document 2", "type": "Invoice"},
            {"id": 3, "name": "Document 3", "type": "Contract"}
        ]
    
    @pytest.fixture
    def excel_file(self, temp_dir, sample_data):
        """Create sample Excel file."""
        file_path = temp_dir / "test_data.xlsx"
        df = pd.DataFrame(sample_data)
        df.to_excel(file_path, index=False)
        return file_path
    
    @pytest.fixture
    def csv_file(self, temp_dir, sample_data):
        """Create sample CSV file."""
        file_path = temp_dir / "test_data.csv"
        df = pd.DataFrame(sample_data)
        df.to_csv(file_path, index=False)
        return file_path
    
    @pytest.fixture
    def json_file(self, temp_dir, sample_data):
        """Create sample JSON file."""
        file_path = temp_dir / "test_data.json"
        with open(file_path, 'w') as f:
            json.dump(sample_data, f)
        return file_path
    
    def test_node_creation(self):
        """Test basic node creation."""
        config = {
            'file_path': '/path/to/file.xlsx',
            'file_type': 'excel',
            'encoding': 'utf-8'
        }
        
        node = FileInputNode("file_input_1", config)
        
        assert node.node_id == "file_input_1"
        assert node.file_path == '/path/to/file.xlsx'
        assert node.file_type == 'excel'
        assert node.encoding == 'utf-8'
        assert node.skip_rows == 0
        assert node.max_rows is None
        assert node.column_mappings == {}
    
    def test_validation_missing_config(self):
        """Test validation with missing configuration."""
        node = FileInputNode("file_input_1", {})
        input_data = NodeInput(data={})
        
        results = node.validate_input(input_data)
        
        # Should have errors for missing file_path
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert len(error_results) > 0
        assert any("file_path" in r.message for r in error_results)
    
    def test_validation_file_not_found(self):
        """Test validation with non-existent file."""
        config = {'file_path': '/nonexistent/file.xlsx'}
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("does not exist" in r.message for r in error_results)
    
    def test_validation_unsupported_format(self, temp_dir):
        """Test validation with unsupported file format."""
        unsupported_file = temp_dir / "test.txt"
        unsupported_file.write_text("test content")
        
        config = {'file_path': str(unsupported_file)}
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Unsupported file format" in r.message for r in error_results)
    
    def test_validation_auto_detect(self, excel_file):
        """Test auto-detection of file type."""
        config = {
            'file_path': str(excel_file),
            'file_type': 'auto'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        results = node.validate_input(input_data)
        
        # Should have info message about auto-detection
        info_results = [r for r in results if r.severity == ValidationSeverity.INFO]
        assert any("Auto-detected file type: excel" in r.message for r in info_results)
    
    def test_validation_invalid_skip_rows(self):
        """Test validation with invalid skip_rows."""
        config = {
            'file_path': '/path/to/file.xlsx',
            'skip_rows': -1
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("skip_rows must be non-negative" in r.message for r in error_results)
    
    def test_validation_invalid_max_rows(self):
        """Test validation with invalid max_rows."""
        config = {
            'file_path': '/path/to/file.xlsx',
            'max_rows': 0
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("max_rows must be positive" in r.message for r in error_results)
    
    def test_process_excel_file(self, excel_file, sample_data):
        """Test processing Excel file."""
        config = {
            'file_path': str(excel_file),
            'file_type': 'excel'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert len(output.errors) == 0
        assert output.data['data'] == sample_data
        
        # Check file info
        file_info = output.data['file_info']
        assert file_info['file_type'] == 'excel'
        assert file_info['rows_read'] == 3
        assert 'id' in file_info['columns']
        assert 'name' in file_info['columns']
        assert 'type' in file_info['columns']
    
    def test_process_csv_file(self, csv_file, sample_data):
        """Test processing CSV file."""
        config = {
            'file_path': str(csv_file),
            'file_type': 'csv'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert len(output.errors) == 0
        assert output.data['data'] == sample_data
        
        file_info = output.data['file_info']
        assert file_info['file_type'] == 'csv'
        assert file_info['rows_read'] == 3
    
    def test_process_json_file(self, json_file, sample_data):
        """Test processing JSON file."""
        config = {
            'file_path': str(json_file),
            'file_type': 'json'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert len(output.errors) == 0
        assert output.data['data'] == sample_data
        
        file_info = output.data['file_info']
        assert file_info['file_type'] == 'json'
        assert file_info['rows_read'] == 3
    
    def test_process_with_skip_rows(self, csv_file):
        """Test processing with skip_rows parameter."""
        config = {
            'file_path': str(csv_file),
            'file_type': 'csv',
            'skip_rows': 1
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        # Should have 2 rows instead of 3 (skipped 1)
        assert output.data['file_info']['rows_read'] == 2
    
    def test_process_with_max_rows(self, csv_file):
        """Test processing with max_rows parameter."""
        config = {
            'file_path': str(csv_file),
            'file_type': 'csv',
            'max_rows': 2
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        # Should have only 2 rows
        assert output.data['file_info']['rows_read'] == 2
    
    def test_process_with_column_mappings(self, csv_file):
        """Test processing with column mappings."""
        config = {
            'file_path': str(csv_file),
            'file_type': 'csv',
            'column_mappings': {'id': 'document_id', 'name': 'document_name'}
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        
        # Check that columns were renamed
        data = output.data['data']
        assert 'document_id' in data[0]
        assert 'document_name' in data[0]
        assert 'id' not in data[0]
        assert 'name' not in data[0]
    
    def test_process_auto_detect_excel(self, excel_file):
        """Test auto-detection of Excel file type."""
        config = {
            'file_path': str(excel_file),
            'file_type': 'auto'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output.data['file_info']['file_type'] == 'excel'
    
    def test_process_empty_file(self, temp_dir):
        """Test processing empty file."""
        empty_file = temp_dir / "empty.csv"
        empty_file.write_text("column1,column2\n")  # Header only
        
        config = {
            'file_path': str(empty_file),
            'file_type': 'csv'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output.data['file_info']['rows_read'] == 0
        assert output.data['data'] == []
    
    def test_process_nonexistent_file(self):
        """Test processing non-existent file."""
        config = {
            'file_path': '/nonexistent/file.csv',
            'file_type': 'csv'
        }
        node = FileInputNode("file_input_1", config)
        input_data = NodeInput(data={})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.FAILED
        assert len(output.errors) > 0
        assert any("No such file" in error or "cannot find" in error.lower() 
                  for error in output.errors)
    
    def test_get_schema(self):
        """Test schema retrieval."""
        node = FileInputNode("file_input_1")
        schema = node.get_schema()
        
        assert schema['node_type'] == 'FileInputNode'
        assert 'description' in schema
        assert 'config_schema' in schema
        assert 'input_schema' in schema
        assert 'output_schema' in schema
        
        # Check output schema structure
        output_schema = schema['output_schema']
        assert 'data' in output_schema['properties']
        assert 'file_info' in output_schema['properties']


if __name__ == "__main__":
    pytest.main([__file__])