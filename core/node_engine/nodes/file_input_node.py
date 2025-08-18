"""
File input node implementation for reading Excel/CSV files.

This module provides a robust file input node that can read various file formats
with comprehensive error handling and validation.
"""

import os
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import pandas as pd

from core.node_interfaces import (
    ProcessingNode, NodeInput, NodeOutput, ValidationResult, 
    ValidationSeverity, NodeStatus
)
from utils.validation_schemas import get_validator


logger = logging.getLogger(__name__)


class FileInputNode(ProcessingNode):
    """
    Node for reading files (Excel, CSV, JSON) with error handling.
    
    Supports various file formats and provides comprehensive error handling
    and data validation capabilities.
    """
    
    SUPPORTED_FORMATS = {
        '.xlsx': 'excel',
        '.xls': 'excel', 
        '.csv': 'csv',
        '.json': 'json'
    }
    
    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the file input node.
        
        Args:
            node_id: Unique identifier for this node instance.
            config: Configuration dictionary containing file input parameters.
        """
        super().__init__(node_id, config)
        
        # Parse configuration
        self.file_path = config.get('file_path', '') if config else ''
        self.file_type = config.get('file_type', 'auto') if config else 'auto'
        self.encoding = config.get('encoding', 'utf-8') if config else 'utf-8'
        self.sheet_name = config.get('sheet_name') if config else None
        self.skip_rows = config.get('skip_rows', 0) if config else 0
        self.max_rows = config.get('max_rows') if config else None
        self.column_mappings = config.get('column_mappings', {}) if config else {}
        
        # Validator for schema checking
        self.validator = get_validator()
        
    def validate_input(self, input_data: NodeInput) -> List[ValidationResult]:
        """
        Validate input data and configuration.
        
        Args:
            input_data: The input data to validate.
            
        Returns:
            List of validation results.
        """
        results = []
        
        # Validate configuration schema
        config_errors = self.validator.validate_node_config(self.config, 'file_input')
        for error in config_errors:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Configuration error: {error}",
                field_name="config",
                error_code="INVALID_CONFIG"
            ))
        
        # Validate required configuration fields
        required_fields = ['file_path']
        missing_fields = [field for field in required_fields if not getattr(self, field)]
        
        for field in missing_fields:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Required configuration field '{field}' is missing or empty",
                field_name=field,
                error_code="MISSING_REQUIRED_CONFIG"
            ))
        
        # Validate file existence and accessibility
        if self.file_path:
            file_path = Path(self.file_path)
            
            if not file_path.exists():
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"File does not exist: {self.file_path}",
                    field_name="file_path",
                    error_code="FILE_NOT_FOUND"
                ))
            elif not file_path.is_file():
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Path is not a file: {self.file_path}",
                    field_name="file_path",
                    error_code="NOT_A_FILE"
                ))
            elif not os.access(file_path, os.R_OK):
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"File is not readable: {self.file_path}",
                    field_name="file_path",
                    error_code="FILE_NOT_READABLE"
                ))
            else:
                # Validate file format
                file_ext = file_path.suffix.lower()
                if file_ext not in self.SUPPORTED_FORMATS:
                    results.append(ValidationResult(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Unsupported file format: {file_ext}. Supported: {list(self.SUPPORTED_FORMATS.keys())}",
                        field_name="file_path",
                        error_code="UNSUPPORTED_FORMAT"
                    ))
                
                # Auto-detect file type if needed
                if self.file_type == 'auto':
                    detected_type = self.SUPPORTED_FORMATS.get(file_ext)
                    if detected_type:
                        results.append(ValidationResult(
                            is_valid=True,
                            severity=ValidationSeverity.INFO,
                            message=f"Auto-detected file type: {detected_type}",
                            field_name="file_type"
                        ))
        
        # Validate numeric parameters
        if self.skip_rows < 0:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="skip_rows must be non-negative",
                field_name="skip_rows",
                error_code="INVALID_SKIP_ROWS"
            ))
        
        if self.max_rows is not None and self.max_rows <= 0:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="max_rows must be positive if specified",
                field_name="max_rows",
                error_code="INVALID_MAX_ROWS"
            ))
        
        # If no errors, add success validation
        if not any(r.severity == ValidationSeverity.ERROR for r in results):
            results.append(ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Input validation passed"
            ))
        
        return results
    
    def process(self, input_data: NodeInput) -> NodeOutput:
        """
        Process the input data by reading the specified file.
        
        Args:
            input_data: The input data containing file reading parameters.
            
        Returns:
            NodeOutput containing the file data and metadata.
        """
        start_time = time.perf_counter()
        
        try:
            # Update memory usage tracking
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Determine file type
            file_path = Path(self.file_path)
            file_ext = file_path.suffix.lower()
            actual_file_type = self.file_type
            
            if actual_file_type == 'auto':
                actual_file_type = self.SUPPORTED_FORMATS.get(file_ext, 'unknown')
            
            logger.info(f"Reading {actual_file_type} file: {self.file_path}")
            
            # Read file based on type
            if actual_file_type == 'excel':
                data = self._read_excel_file(file_path)
            elif actual_file_type == 'csv':
                data = self._read_csv_file(file_path)
            elif actual_file_type == 'json':
                data = self._read_json_file(file_path)
            else:
                raise ValueError(f"Unsupported file type: {actual_file_type}")
            
            # Apply column mappings if specified
            if self.column_mappings and isinstance(data, pd.DataFrame):
                data = data.rename(columns=self.column_mappings)
            
            # Track final memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = final_memory - initial_memory
            self._update_memory_usage(memory_used)
            
            # Calculate processing time
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Prepare output data
            output_data = {
                'data': data.to_dict('records') if isinstance(data, pd.DataFrame) else data,
                'file_info': {
                    'file_path': str(file_path.absolute()),
                    'file_size_bytes': file_path.stat().st_size,
                    'file_type': actual_file_type,
                    'rows_read': len(data) if isinstance(data, (pd.DataFrame, list)) else 1,
                    'columns': list(data.columns) if isinstance(data, pd.DataFrame) else [],
                    'encoding': self.encoding,
                    'memory_used_mb': memory_used
                }
            }
            
            # Create output with metadata
            output = self._create_output(output_data, processing_time_ms)
            output.metadata.update({
                'source_file': str(file_path),
                'file_type': actual_file_type,
                'records_count': len(data) if isinstance(data, (pd.DataFrame, list)) else 1,
                'memory_usage_mb': memory_used
            })
            
            logger.info(f"Successfully read {output_data['file_info']['rows_read']} records from {self.file_path}")
            return output
            
        except Exception as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Failed to read file {self.file_path}: {e}", exc_info=True)
            
            # Create error output
            output = NodeOutput(
                data={},
                node_id=self.node_id,
                status=NodeStatus.FAILED,
                processing_time_ms=processing_time_ms,
                errors=[str(e)]
            )
            return output
    
    def _read_excel_file(self, file_path: Path) -> pd.DataFrame:
        """Read Excel file with error handling."""
        read_params = {
            'skiprows': self.skip_rows,
            'nrows': self.max_rows
        }
        
        if self.sheet_name is not None:
            read_params['sheet_name'] = self.sheet_name
        
        try:
            # First try with openpyxl (more robust for .xlsx)
            if file_path.suffix.lower() == '.xlsx':
                read_params['engine'] = 'openpyxl'
            else:
                # Use xlrd for .xls files
                read_params['engine'] = 'xlrd'
            
            df = pd.read_excel(file_path, **read_params)
            
            # Handle empty DataFrames
            if df.empty:
                logger.warning(f"Excel file {file_path} is empty or contains no data")
                return pd.DataFrame()
            
            return df
            
        except Exception as e:
            # Try alternative engine if the first one fails
            logger.warning(f"Primary Excel engine failed for {file_path}, trying alternative: {e}")
            
            if 'engine' in read_params:
                # Try without specifying engine
                del read_params['engine']
                return pd.read_excel(file_path, **read_params)
            else:
                raise e
    
    def _read_csv_file(self, file_path: Path) -> pd.DataFrame:
        """Read CSV file with error handling."""
        read_params = {
            'encoding': self.encoding,
            'skiprows': self.skip_rows,
            'nrows': self.max_rows
        }
        
        try:
            df = pd.read_csv(file_path, **read_params)
            
            if df.empty:
                logger.warning(f"CSV file {file_path} is empty or contains no data")
                return pd.DataFrame()
            
            return df
            
        except UnicodeDecodeError as e:
            # Try alternative encodings
            logger.warning(f"Encoding {self.encoding} failed for {file_path}, trying alternatives")
            
            alternative_encodings = ['gbk', 'gb2312', 'utf-8-sig', 'latin1']
            for encoding in alternative_encodings:
                if encoding != self.encoding:
                    try:
                        read_params['encoding'] = encoding
                        df = pd.read_csv(file_path, **read_params)
                        logger.info(f"Successfully read CSV with encoding: {encoding}")
                        return df
                    except UnicodeDecodeError:
                        continue
            
            # If all encodings fail, raise the original error
            raise e
    
    def _read_json_file(self, file_path: Path) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """Read JSON file with error handling."""
        try:
            # Try to read as DataFrame first (for structured JSON)
            df = pd.read_json(file_path, encoding=self.encoding)
            
            # Apply row limits if specified
            if self.skip_rows > 0:
                df = df.iloc[self.skip_rows:]
            
            if self.max_rows is not None:
                df = df.head(self.max_rows)
            
            return df
            
        except ValueError:
            # If DataFrame reading fails, read as raw JSON
            import json
            
            with open(file_path, 'r', encoding=self.encoding) as f:
                data = json.load(f)
            
            # Handle list of records
            if isinstance(data, list):
                # Apply row limits
                if self.skip_rows > 0:
                    data = data[self.skip_rows:]
                
                if self.max_rows is not None:
                    data = data[:self.max_rows]
            
            return data
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's configuration and input/output.
        
        Returns:
            A dictionary containing the JSON schema definition.
        """
        return {
            "node_type": "FileInputNode",
            "description": "Reads data from Excel, CSV, or JSON files",
            "config_schema": self.validator.get_schema('file_input_node_config'),
            "input_schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Optional override parameters"
                    }
                },
                "additionalProperties": True
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object"
                        },
                        "description": "Array of records read from the file"
                    },
                    "file_info": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "file_size_bytes": {"type": "integer"},
                            "file_type": {"type": "string"},
                            "rows_read": {"type": "integer"},
                            "columns": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "encoding": {"type": "string"},
                            "memory_used_mb": {"type": "number"}
                        }
                    }
                },
                "required": ["data", "file_info"]
            }
        }