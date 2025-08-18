"""
File output node implementation for Excel generation.

This module provides a file output node that generates Excel files using
the existing generator.py functionality, ensuring compatibility with
the legacy system while providing node-based interface.
"""

import os
import logging
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import pandas as pd

from core.node_interfaces import (
    ProcessingNode, NodeInput, NodeOutput, ValidationResult, 
    ValidationSeverity, NodeStatus
)
from utils.validation_schemas import get_validator


logger = logging.getLogger(__name__)


class FileOutputNode(ProcessingNode):
    """
    Node for generating Excel files from data using the existing generator.
    
    Integrates with the legacy generator.py system to produce Excel directory
    files while providing a modern node-based interface.
    """
    
    SUPPORTED_FORMATS = ['excel', 'csv', 'json']
    
    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the file output node.
        
        Args:
            node_id: Unique identifier for this node instance.
            config: Configuration dictionary containing output parameters.
        """
        super().__init__(node_id, config)
        
        # Parse configuration
        self.output_path = config.get('output_path', '') if config else ''
        self.template_path = config.get('template_path') if config else None
        self.format = config.get('format', 'excel') if config else 'excel'
        self.overwrite = config.get('overwrite', False) if config else False
        self.excel_options = config.get('excel_options', {}) if config else {}
        
        # Validator for schema checking
        self.validator = get_validator()
        
        # Statistics tracking
        self.stats = {
            'records_written': 0,
            'files_created': 0,
            'bytes_written': 0
        }
    
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
        config_errors = self.validator.validate_node_config(self.config, 'file_output')
        for error in config_errors:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Configuration error: {error}",
                field_name="config",
                error_code="INVALID_CONFIG"
            ))
        
        # Validate required configuration fields
        if not self.output_path:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Output path is required",
                field_name="output_path",
                error_code="MISSING_OUTPUT_PATH"
            ))
        
        # Validate output format
        if self.format not in self.SUPPORTED_FORMATS:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Unsupported format: {self.format}. Supported: {self.SUPPORTED_FORMATS}",
                field_name="format",
                error_code="UNSUPPORTED_FORMAT"
            ))
        
        # Validate template path for Excel format
        if self.format == 'excel' and self.template_path:
            template_path = Path(self.template_path)
            if not template_path.exists():
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Template file does not exist: {self.template_path}",
                    field_name="template_path",
                    error_code="TEMPLATE_NOT_FOUND"
                ))
            elif not template_path.is_file():
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Template path is not a file: {self.template_path}",
                    field_name="template_path",
                    error_code="TEMPLATE_NOT_FILE"
                ))
        
        # Validate output directory
        output_path = Path(self.output_path)
        output_dir = output_path.parent
        
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                results.append(ValidationResult(
                    is_valid=True,
                    severity=ValidationSeverity.INFO,
                    message=f"Created output directory: {output_dir}",
                    field_name="output_path"
                ))
            except Exception as e:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Cannot create output directory: {e}",
                    field_name="output_path",
                    error_code="CANNOT_CREATE_DIR"
                ))
        
        # Check if output file exists and overwrite setting
        if output_path.exists() and not self.overwrite:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Output file exists and overwrite is disabled: {self.output_path}",
                field_name="output_path",
                error_code="FILE_EXISTS"
            ))
        
        # Validate input data contains 'data' field
        if not input_data.has_key('data'):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Input data must contain 'data' field",
                field_name="data",
                error_code="MISSING_DATA_FIELD"
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
        Process the input data by generating output files.
        
        Args:
            input_data: The input data containing records to write.
            
        Returns:
            NodeOutput containing file generation results.
        """
        start_time = time.perf_counter()
        
        try:
            # Reset statistics
            self.stats = {
                'records_written': 0,
                'files_created': 0,
                'bytes_written': 0
            }
            
            # Get input data
            raw_data = input_data.get_value('data')
            if raw_data is None:
                raise ValueError("Input data is empty")
            
            # Convert to DataFrame for processing
            if isinstance(raw_data, list):
                if not raw_data:  # Empty list
                    logger.warning("No data to write")
                    return self._create_empty_output(start_time)
                df = pd.DataFrame(raw_data)
            elif isinstance(raw_data, dict):
                df = pd.DataFrame([raw_data])
            elif isinstance(raw_data, pd.DataFrame):
                if raw_data.empty:
                    logger.warning("No data to write")
                    return self._create_empty_output(start_time)
                df = raw_data.copy()
            else:
                raise ValueError(f"Unsupported data type: {type(raw_data)}")
            
            if df.empty:
                logger.warning("No data to write")
                return self._create_empty_output(start_time)
            
            self.stats['records_written'] = len(df)
            
            logger.info(f"Writing {len(df)} records to {self.format} format: {self.output_path}")
            
            # Generate output based on format
            if self.format == 'excel':
                self._write_excel_file(df, input_data)
            elif self.format == 'csv':
                self._write_csv_file(df)
            elif self.format == 'json':
                self._write_json_file(df)
            else:
                raise ValueError(f"Unsupported format: {self.format}")
            
            # Calculate file size
            output_path = Path(self.output_path)
            if output_path.exists():
                self.stats['bytes_written'] = output_path.stat().st_size
                self.stats['files_created'] = 1
            
            # Calculate processing time and memory usage
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Track memory usage
            import psutil
            process = psutil.Process()
            memory_used = process.memory_info().rss / 1024 / 1024  # MB
            self._update_memory_usage(memory_used)
            
            # Prepare output data
            output_data = {
                'output_file': str(output_path.absolute()),
                'statistics': self.stats.copy(),
                'file_info': {
                    'format': self.format,
                    'size_bytes': self.stats['bytes_written'],
                    'records_written': self.stats['records_written'],
                    'memory_used_mb': memory_used
                }
            }
            
            # Create output with metadata
            output = self._create_output(output_data, processing_time_ms)
            output.metadata.update({
                'output_file': str(output_path),
                'format': self.format,
                'records_written': self.stats['records_written'],
                'file_size_bytes': self.stats['bytes_written'],
                'memory_usage_mb': memory_used
            })
            
            logger.info(f"Successfully wrote {self.stats['records_written']} records to {output_path}")
            return output
            
        except Exception as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            return self._handle_generation_error(e, processing_time_ms)
    
    def _handle_generation_error(self, e: Exception, processing_time_ms: float) -> NodeOutput:
        """Centralized error handling for file generation failures."""
        error_message = str(e)
        logger.error(f"File output failed: {error_message}", exc_info=True)
        
        # Add specific error context based on exception type
        if isinstance(e, PermissionError):
            error_message = f"Permission denied writing to {self.output_path}: {error_message}"
        elif isinstance(e, FileNotFoundError):
            error_message = f"Output directory not found: {error_message}"
        elif isinstance(e, OSError):
            error_message = f"File system error: {error_message}"
        
        return NodeOutput(
            data={'statistics': self.stats},
            node_id=self.node_id,
            status=NodeStatus.FAILED,
            processing_time_ms=processing_time_ms,
            errors=[error_message]
        )
    
    def _write_excel_file(self, df: pd.DataFrame, input_data: NodeInput) -> None:
        """Write data to Excel file using existing generator functionality."""
        try:
            # If we have a template, use it
            if self.template_path:
                self._write_excel_with_template(df, input_data)
            else:
                self._write_excel_simple(df)
        except Exception as e:
            logger.error(f"Excel generation failed: {e}")
            raise e
    
    def _write_excel_with_template(self, df: pd.DataFrame, input_data: NodeInput) -> None:
        """Write Excel using template and existing generator logic."""
        try:
            # Import the existing generator functionality
            from core.generator import generate_directory_excel
            from core.enhanced_height_calculator import get_height_calculator
            
            # Prepare parameters for the generator
            generator_params = {
                'template_path': self.template_path,
                'output_path': self.output_path,
                'data': df,
                'height_calculator': get_height_calculator(),
                'excel_options': self.excel_options
            }
            
            # Get additional configuration from input metadata
            directory_config = input_data.metadata.get('directory_config', {})
            if directory_config:
                generator_params.update(directory_config)
            
            # Call the existing generator
            logger.info(f"Using template-based Excel generation with {self.template_path}")
            generate_directory_excel(**generator_params)
            
        except ImportError:
            logger.warning("Core generator not available, falling back to simple Excel generation")
            self._write_excel_simple(df)
        except Exception as e:
            logger.error(f"Template-based Excel generation failed: {e}")
            # Fallback to simple generation
            self._write_excel_simple(df)
    
    def _write_excel_simple(self, df: pd.DataFrame) -> None:
        """Write Excel file using simple pandas ExcelWriter."""
        excel_options = self.excel_options.copy()
        
        # Extract sheet name
        sheet_name = excel_options.pop('sheet_name', 'Sheet1')
        start_row = excel_options.pop('start_row', 0)
        start_col = excel_options.pop('start_col', 0)
        auto_fit = excel_options.pop('auto_fit', True)
        
        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
            # Write the data
            df.to_excel(
                writer, 
                sheet_name=sheet_name,
                startrow=start_row,
                startcol=start_col,
                index=False
            )
            
            # Apply formatting if requested
            if auto_fit:
                worksheet = writer.sheets[sheet_name]
                
                # Auto-fit columns
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    
                    adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Apply page setup if specified
            page_setup = excel_options.get('page_setup', {})
            if page_setup:
                worksheet = writer.sheets[sheet_name]
                
                if 'orientation' in page_setup:
                    from openpyxl.worksheet.page import PageMargins
                    if page_setup['orientation'] == 'landscape':
                        worksheet.page_setup.orientation = worksheet.ORIENTATION_LANDSCAPE
                    else:
                        worksheet.page_setup.orientation = worksheet.ORIENTATION_PORTRAIT
                
                if 'margins' in page_setup:
                    margins = page_setup['margins']
                    worksheet.page_margins = PageMargins(
                        left=margins.get('left', 0.7),
                        right=margins.get('right', 0.7),
                        top=margins.get('top', 0.75),
                        bottom=margins.get('bottom', 0.75)
                    )
    
    def _write_csv_file(self, df: pd.DataFrame) -> None:
        """Write data to CSV file."""
        df.to_csv(self.output_path, index=False, encoding='utf-8-sig')
    
    def _write_json_file(self, df: pd.DataFrame) -> None:
        """Write data to JSON file."""
        data = df.to_dict('records')
        
        import json
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _create_empty_output(self, start_time: float) -> NodeOutput:
        """Create output for empty data case."""
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        output_data = {
            'output_file': self.output_path,
            'statistics': self.stats.copy(),
            'file_info': {
                'format': self.format,
                'size_bytes': 0,
                'records_written': 0,
                'memory_used_mb': 0
            }
        }
        
        output = self._create_output(output_data, processing_time_ms)
        output.add_warning("No data provided, output file not created")
        
        return output
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's configuration and input/output.
        
        Returns:
            A dictionary containing the JSON schema definition.
        """
        return {
            "node_type": "FileOutputNode",
            "description": "Writes data to Excel, CSV, or JSON files with template support",
            "config_schema": self.validator.get_schema('file_output_node_config'),
            "supported_formats": self.SUPPORTED_FORMATS,
            "input_schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "oneOf": [
                            {
                                "type": "array",
                                "items": {"type": "object"}
                            },
                            {
                                "type": "object"
                            }
                        ],
                        "description": "Data to write to file"
                    }
                },
                "required": ["data"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "output_file": {
                        "type": "string",
                        "description": "Path to the generated output file"
                    },
                    "statistics": {
                        "type": "object",
                        "properties": {
                            "records_written": {"type": "integer"},
                            "files_created": {"type": "integer"},
                            "bytes_written": {"type": "integer"}
                        }
                    },
                    "file_info": {
                        "type": "object",
                        "properties": {
                            "format": {"type": "string"},
                            "size_bytes": {"type": "integer"},
                            "records_written": {"type": "integer"},
                            "memory_used_mb": {"type": "number"}
                        }
                    }
                },
                "required": ["output_file", "statistics", "file_info"]
            }
        }