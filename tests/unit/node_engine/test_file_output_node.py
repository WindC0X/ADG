"""
Unit tests for FileOutputNode.

Tests file output functionality for Excel, CSV, and JSON formats
with template support and comprehensive error handling.
"""

import pytest
import tempfile
import json
import pandas as pd
from pathlib import Path

from core.node_interfaces import NodeInput, NodeStatus, ValidationSeverity
from core.node_engine.nodes.file_output_node import FileOutputNode


class TestFileOutputNode:
    """Test FileOutputNode functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_data(self):
        """Sample data for testing output."""
        return [
            {"id": 1, "name": "Document 1", "type": "Report", "value": 100.5},
            {"id": 2, "name": "Document 2", "type": "Invoice", "value": 250.0},
            {"id": 3, "name": "Document 3", "type": "Contract", "value": 500.0}
        ]
    
    @pytest.fixture
    def excel_template(self, temp_dir):
        """Create a simple Excel template."""
        template_path = temp_dir / "template.xlsx"
        
        # Create a simple template with headers
        df = pd.DataFrame(columns=["id", "name", "type", "value"])
        df.to_excel(template_path, index=False)
        
        return template_path
    
    def test_node_creation(self, temp_dir):
        """Test basic node creation."""
        output_path = str(temp_dir / "output.xlsx")
        config = {
            'output_path': output_path,
            'format': 'excel',
            'overwrite': True
        }
        
        node = FileOutputNode("file_output_1", config)
        
        assert node.node_id == "file_output_1"
        assert node.output_path == output_path
        assert node.format == 'excel'
        assert node.overwrite is True
        assert node.template_path is None
        assert node.excel_options == {}
    
    def test_validation_missing_output_path(self):
        """Test validation with missing output path."""
        node = FileOutputNode("file_output_1", {})
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Output path is required" in r.message for r in error_results)
    
    def test_validation_unsupported_format(self, temp_dir):
        """Test validation with unsupported format."""
        config = {
            'output_path': str(temp_dir / "output.txt"),
            'format': 'unsupported'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Unsupported format" in r.message for r in error_results)
    
    def test_validation_template_not_found(self, temp_dir):
        """Test validation with non-existent template."""
        config = {
            'output_path': str(temp_dir / "output.xlsx"),
            'format': 'excel',
            'template_path': '/nonexistent/template.xlsx'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("Template file does not exist" in r.message for r in error_results)
    
    def test_validation_file_exists_no_overwrite(self, temp_dir):
        """Test validation when file exists and overwrite is disabled."""
        output_file = temp_dir / "existing.xlsx"
        output_file.write_text("existing content")
        
        config = {
            'output_path': str(output_file),
            'format': 'excel',
            'overwrite': False
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("file exists and overwrite is disabled" in r.message.lower() for r in error_results)
    
    def test_validation_missing_data_field(self, temp_dir):
        """Test validation with missing data field."""
        config = {
            'output_path': str(temp_dir / "output.xlsx"),
            'format': 'excel'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={})  # Missing 'data' key
        
        results = node.validate_input(input_data)
        
        error_results = [r for r in results if r.severity == ValidationSeverity.ERROR]
        assert any("must contain 'data' field" in r.message for r in error_results)
    
    def test_validation_creates_output_directory(self, temp_dir):
        """Test validation creates output directory if it doesn't exist."""
        new_dir = temp_dir / "new_subdir"
        output_path = new_dir / "output.xlsx"
        
        config = {
            'output_path': str(output_path),
            'format': 'excel'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": []})
        
        results = node.validate_input(input_data)
        
        # Should create the directory and have info message
        assert new_dir.exists()
        info_results = [r for r in results if r.severity == ValidationSeverity.INFO]
        assert any("Created output directory" in r.message for r in info_results)
    
    def test_process_excel_simple(self, temp_dir, sample_data):
        """Test simple Excel output without template."""
        output_path = temp_dir / "output.xlsx"
        config = {
            'output_path': str(output_path),
            'format': 'excel'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert len(output.errors) == 0
        assert output_path.exists()
        
        # Verify file content
        df = pd.read_excel(output_path)
        assert len(df) == 3
        assert list(df.columns) == ["id", "name", "type", "value"]
        assert df.iloc[0]['name'] == 'Document 1'
        
        # Check output data
        file_info = output.data['file_info']
        assert file_info['format'] == 'excel'
        assert file_info['records_written'] == 3
        assert file_info['size_bytes'] > 0
    
    def test_process_csv_output(self, temp_dir, sample_data):
        """Test CSV output."""
        output_path = temp_dir / "output.csv"
        config = {
            'output_path': str(output_path),
            'format': 'csv'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # Verify file content
        df = pd.read_csv(output_path)
        assert len(df) == 3
        assert df.iloc[0]['name'] == 'Document 1'
        
        file_info = output.data['file_info']
        assert file_info['format'] == 'csv'
        assert file_info['records_written'] == 3
    
    def test_process_json_output(self, temp_dir, sample_data):
        """Test JSON output."""
        output_path = temp_dir / "output.json"
        config = {
            'output_path': str(output_path),
            'format': 'json'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # Verify file content
        with open(output_path, 'r') as f:
            data = json.load(f)
        
        assert len(data) == 3
        assert data[0]['name'] == 'Document 1'
        
        file_info = output.data['file_info']
        assert file_info['format'] == 'json'
        assert file_info['records_written'] == 3
    
    def test_process_excel_with_options(self, temp_dir, sample_data):
        """Test Excel output with custom options."""
        output_path = temp_dir / "output.xlsx"
        config = {
            'output_path': str(output_path),
            'format': 'excel',
            'excel_options': {
                'sheet_name': 'CustomSheet',
                'start_row': 2,
                'start_col': 1,
                'auto_fit': True
            }
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # Verify file content - should have data starting at row 2, column 1
        df = pd.read_excel(output_path, sheet_name='CustomSheet', header=2)
        assert len(df) == 3
    
    def test_process_with_template_fallback(self, temp_dir, sample_data):
        """Test Excel output with template (fallback to simple when template processing fails)."""
        output_path = temp_dir / "output.xlsx"
        
        # Create a minimal template file
        template_path = temp_dir / "template.xlsx"
        template_df = pd.DataFrame(columns=["id", "name", "type", "value"])
        template_df.to_excel(template_path, index=False)
        
        config = {
            'output_path': str(output_path),
            'format': 'excel',
            'template_path': str(template_path)
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        # Should succeed even if template processing fails (fallback to simple)
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # Verify basic content
        df = pd.read_excel(output_path)
        assert len(df) == 3
    
    def test_process_empty_data(self, temp_dir):
        """Test processing with empty data."""
        output_path = temp_dir / "output.xlsx"
        config = {
            'output_path': str(output_path),
            'format': 'excel'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": []})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert len(output.warnings) > 0
        assert any("No data provided" in warning for warning in output.warnings)
        
        file_info = output.data['file_info']
        assert file_info['records_written'] == 0
        assert file_info['size_bytes'] == 0
    
    def test_process_single_record(self, temp_dir):
        """Test processing with single record (dict instead of list)."""
        output_path = temp_dir / "output.csv"
        config = {
            'output_path': str(output_path),
            'format': 'csv'
        }
        node = FileOutputNode("file_output_1", config)
        
        single_record = {"id": 1, "name": "Single Document", "type": "Report"}
        input_data = NodeInput(data={"data": single_record})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # Verify content
        df = pd.read_csv(output_path)
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'Single Document'
        
        file_info = output.data['file_info']
        assert file_info['records_written'] == 1
    
    def test_process_dataframe_input(self, temp_dir, sample_data):
        """Test processing with DataFrame input."""
        output_path = temp_dir / "output.csv"
        config = {
            'output_path': str(output_path),
            'format': 'csv'
        }
        node = FileOutputNode("file_output_1", config)
        
        df_input = pd.DataFrame(sample_data)
        input_data = NodeInput(data={"data": df_input})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # Verify content
        df = pd.read_csv(output_path)
        assert len(df) == 3
        
        file_info = output.data['file_info']
        assert file_info['records_written'] == 3
    
    def test_process_invalid_output_path(self, temp_dir):
        """Test processing with invalid output path."""
        # Try to write to a directory instead of a file
        config = {
            'output_path': str(temp_dir),  # Directory, not file
            'format': 'excel'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": [{"test": "data"}]})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.FAILED
        assert len(output.errors) > 0
    
    def test_process_unsupported_data_type(self, temp_dir):
        """Test processing with unsupported data type."""
        output_path = temp_dir / "output.csv"
        config = {
            'output_path': str(output_path),
            'format': 'csv'
        }
        node = FileOutputNode("file_output_1", config)
        
        # String data instead of dict/list/DataFrame
        input_data = NodeInput(data={"data": "invalid_data_type"})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.FAILED
        assert len(output.errors) > 0
        assert any("Unsupported data type" in error for error in output.errors)
    
    def test_process_missing_data(self, temp_dir):
        """Test processing with missing data field."""
        output_path = temp_dir / "output.csv"
        config = {
            'output_path': str(output_path),
            'format': 'csv'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={})  # No data field
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.FAILED
        assert len(output.errors) > 0
        assert any("Input data is empty" in error for error in output.errors)
    
    def test_overwrite_existing_file(self, temp_dir, sample_data):
        """Test overwriting existing file."""
        output_path = temp_dir / "existing.csv"
        
        # Create existing file
        output_path.write_text("existing,content\n1,test")
        original_size = output_path.stat().st_size
        
        config = {
            'output_path': str(output_path),
            'format': 'csv',
            'overwrite': True
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        assert output_path.exists()
        
        # File should be overwritten and have different size
        new_size = output_path.stat().st_size
        assert new_size != original_size
        
        # Verify new content
        df = pd.read_csv(output_path)
        assert len(df) == 3
        assert df.iloc[0]['name'] == 'Document 1'
    
    def test_statistics_tracking(self, temp_dir, sample_data):
        """Test statistics tracking during output."""
        output_path = temp_dir / "output.json"
        config = {
            'output_path': str(output_path),
            'format': 'json'
        }
        node = FileOutputNode("file_output_1", config)
        input_data = NodeInput(data={"data": sample_data})
        
        output = node.process(input_data)
        
        assert output.status == NodeStatus.COMPLETED
        
        stats = output.data['statistics']
        assert stats['records_written'] == 3
        assert stats['files_created'] == 1
        assert stats['bytes_written'] > 0
        
        file_info = output.data['file_info']
        assert file_info['records_written'] == 3
        assert file_info['size_bytes'] > 0
        assert file_info['memory_used_mb'] >= 0
    
    def test_get_schema(self):
        """Test schema retrieval."""
        node = FileOutputNode("file_output_1")
        schema = node.get_schema()
        
        assert schema['node_type'] == 'FileOutputNode'
        assert 'description' in schema
        assert 'config_schema' in schema
        assert 'supported_formats' in schema
        assert 'input_schema' in schema
        assert 'output_schema' in schema
        
        # Check supported formats
        formats = schema['supported_formats']
        assert 'excel' in formats
        assert 'csv' in formats
        assert 'json' in formats
        
        # Check output schema structure
        output_schema = schema['output_schema']
        assert 'output_file' in output_schema['properties']
        assert 'statistics' in output_schema['properties']
        assert 'file_info' in output_schema['properties']


if __name__ == "__main__":
    pytest.main([__file__])