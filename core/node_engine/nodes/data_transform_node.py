"""
Data transformation node implementation for validation and format conversion.

This module provides a flexible data transformation node that can apply
various transformations, validations, and format conversions to data.
"""

import logging
import time
from typing import Dict, Any, List, Optional
import pandas as pd

from core.node_interfaces import (
    ProcessingNode, NodeInput, NodeOutput, ValidationResult, 
    ValidationSeverity, NodeStatus
)
from utils.validation_schemas import get_validator


logger = logging.getLogger(__name__)


class DataTransformNode(ProcessingNode):
    """
    Node for data transformation, validation, and format conversion.
    
    Supports various transformation operations including filtering, mapping,
    validation, formatting, and aggregation.
    """
    
    SUPPORTED_OPERATIONS = {
        'filter': ['equals', 'not_equals', 'contains', 'not_contains', 'regex', 'range', 'in_list'],
        'map': ['rename', 'calculate', 'combine', 'split', 'format'],
        'validate': ['required', 'type', 'format', 'range', 'pattern'],
        'format': ['date', 'number', 'text', 'trim', 'case'],
        'aggregate': ['count', 'sum', 'avg', 'min', 'max', 'group_by']
    }
    
    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data transformation node.
        
        Args:
            node_id: Unique identifier for this node instance.
            config: Configuration dictionary containing transformation parameters.
        """
        super().__init__(node_id, config)
        
        # Parse configuration
        self.transformations = config.get('transformations', []) if config else []
        self.validation_rules = config.get('validation_rules', {}) if config else {}
        self.error_handling = config.get('error_handling', 'strict') if config else 'strict'
        
        # Validator for schema checking
        self.validator = get_validator()
        
        # Statistics tracking
        self.stats = {
            'records_processed': 0,
            'records_filtered': 0,
            'validation_errors': 0,
            'transformation_errors': 0
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
        config_errors = self.validator.validate_node_config(self.config, 'data_transform')
        for error in config_errors:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Configuration error: {error}",
                field_name="config",
                error_code="INVALID_CONFIG"
            ))
        
        # Validate transformations
        if not self.transformations:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="At least one transformation must be specified",
                field_name="transformations",
                error_code="NO_TRANSFORMATIONS"
            ))
        
        for i, transform in enumerate(self.transformations):
            transform_type = transform.get('type')
            operation = transform.get('operation')
            
            if transform_type not in self.SUPPORTED_OPERATIONS:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Unsupported transformation type: {transform_type}",
                    field_name=f"transformations[{i}].type",
                    error_code="UNSUPPORTED_TRANSFORM_TYPE"
                ))
                continue
            
            if operation not in self.SUPPORTED_OPERATIONS[transform_type]:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Unsupported operation '{operation}' for type '{transform_type}'",
                    field_name=f"transformations[{i}].operation",
                    error_code="UNSUPPORTED_OPERATION"
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
        
        # Validate error handling mode
        if self.error_handling not in ['strict', 'skip', 'default']:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid error handling mode: {self.error_handling}",
                field_name="error_handling",
                error_code="INVALID_ERROR_HANDLING"
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
        Process the input data by applying transformations.
        
        Args:
            input_data: The input data containing records to transform.
            
        Returns:
            NodeOutput containing transformed data and statistics.
        """
        start_time = time.perf_counter()
        
        try:
            # Reset statistics
            self.stats = {
                'records_processed': 0,
                'records_filtered': 0,
                'validation_errors': 0,
                'transformation_errors': 0
            }
            
            # Get input data
            raw_data = input_data.get_value('data')
            if not raw_data and raw_data != []:  # Allow empty list but not None
                raise ValueError("Input data is empty")
            
            # Convert to DataFrame for easier processing
            if isinstance(raw_data, list):
                if not raw_data:  # Empty list
                    df = pd.DataFrame()
                else:
                    df = pd.DataFrame(raw_data)
            elif isinstance(raw_data, dict):
                df = pd.DataFrame([raw_data])
            elif isinstance(raw_data, pd.DataFrame):
                df = raw_data.copy()
            else:
                raise ValueError(f"Unsupported data type: {type(raw_data)}")
            
            initial_count = len(df)
            self.stats['records_processed'] = initial_count
            
            logger.info(f"Processing {initial_count} records with {len(self.transformations)} transformations")
            
            # Apply transformations sequentially
            for i, transform in enumerate(self.transformations):
                try:
                    df = self._apply_transformation(df, transform, i)
                except Exception as e:
                    self.stats['transformation_errors'] += 1
                    if self.error_handling == 'strict':
                        raise e
                    else:
                        logger.warning(f"Transformation {i} failed: {e}")
                        continue
            
            final_count = len(df)
            self.stats['records_filtered'] = initial_count - final_count
            
            # Convert back to records format
            transformed_data = df.to_dict('records') if not df.empty else []
            
            # Calculate processing time and memory usage
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Track memory usage
            import psutil
            process = psutil.Process()
            memory_used = process.memory_info().rss / 1024 / 1024  # MB
            self._update_memory_usage(memory_used)
            
            # Prepare output data
            output_data = {
                'data': transformed_data,
                'statistics': self.stats.copy(),
                'transformation_summary': {
                    'initial_records': initial_count,
                    'final_records': final_count,
                    'transformations_applied': len(self.transformations),
                    'memory_used_mb': memory_used
                }
            }
            
            # Create output with metadata
            output = self._create_output(output_data, processing_time_ms)
            output.metadata.update({
                'records_transformed': final_count,
                'transformations_count': len(self.transformations),
                'memory_usage_mb': memory_used,
                'statistics': self.stats
            })
            
            logger.info(f"Successfully transformed {initial_count} -> {final_count} records")
            return output
            
        except Exception as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Data transformation failed: {e}", exc_info=True)
            
            # Create error output
            output = NodeOutput(
                data={'statistics': self.stats},
                node_id=self.node_id,
                status=NodeStatus.FAILED,
                processing_time_ms=processing_time_ms,
                errors=[str(e)]
            )
            return output
    
    def _apply_transformation(self, df: pd.DataFrame, transform: Dict[str, Any], index: int) -> pd.DataFrame:
        """Apply a single transformation to the DataFrame."""
        transform_type = transform['type']
        operation = transform['operation']
        field = transform.get('field')
        parameters = transform.get('parameters', {})
        
        logger.debug(f"Applying transformation {index}: {transform_type}.{operation} on field '{field}'")
        
        if transform_type == 'filter':
            return self._apply_filter(df, operation, field, parameters)
        elif transform_type == 'map':
            return self._apply_map(df, operation, field, parameters)
        elif transform_type == 'validate':
            return self._apply_validation(df, operation, field, parameters)
        elif transform_type == 'format':
            return self._apply_format(df, operation, field, parameters)
        elif transform_type == 'aggregate':
            return self._apply_aggregation(df, operation, field, parameters)
        else:
            raise ValueError(f"Unknown transformation type: {transform_type}")
    
    def _apply_filter(self, df: pd.DataFrame, operation: str, field: str, params: Dict[str, Any]) -> pd.DataFrame:
        """Apply filter operations."""
        if field not in df.columns:
            logger.warning(f"Filter field '{field}' not found in data")
            return df
        
        initial_count = len(df)
        
        if operation == 'equals':
            value = params.get('value')
            filtered_df = df[df[field] == value]
        elif operation == 'not_equals':
            value = params.get('value')
            filtered_df = df[df[field] != value]
        elif operation == 'contains':
            value = params.get('value', '')
            filtered_df = df[df[field].astype(str).str.contains(value, na=False)]
        elif operation == 'not_contains':
            value = params.get('value', '')
            filtered_df = df[~df[field].astype(str).str.contains(value, na=False)]
        elif operation == 'regex':
            pattern = params.get('pattern', '')
            filtered_df = df[df[field].astype(str).str.match(pattern, na=False)]
        elif operation == 'range':
            min_val = params.get('min')
            max_val = params.get('max')
            mask = pd.Series([True] * len(df))
            if min_val is not None:
                mask &= (df[field] >= min_val)
            if max_val is not None:
                mask &= (df[field] <= max_val)
            filtered_df = df[mask]
        elif operation == 'in_list':
            values = params.get('values', [])
            filtered_df = df[df[field].isin(values)]
        else:
            raise ValueError(f"Unknown filter operation: {operation}")
        
        filtered_count = initial_count - len(filtered_df)
        if filtered_count > 0:
            logger.info(f"Filter {operation} on '{field}' removed {filtered_count} records")
        
        return filtered_df
    
    def _apply_map(self, df: pd.DataFrame, operation: str, field: str, params: Dict[str, Any]) -> pd.DataFrame:
        """Apply mapping operations."""
        if operation == 'rename':
            old_name = field
            new_name = params.get('new_name')
            if old_name in df.columns and new_name:
                df = df.rename(columns={old_name: new_name})
        elif operation == 'calculate':
            formula = params.get('formula')
            if formula and field:
                # Simple formula evaluation (can be extended)
                df[field] = df.eval(formula)
        elif operation == 'combine':
            source_fields = params.get('source_fields', [])
            separator = params.get('separator', ' ')
            if source_fields and field:
                df[field] = df[source_fields].astype(str).agg(separator.join, axis=1)
        elif operation == 'split':
            separator = params.get('separator', ' ')
            target_fields = params.get('target_fields', [])
            if field in df.columns and target_fields:
                split_data = df[field].astype(str).str.split(separator, expand=True)
                for i, target_field in enumerate(target_fields):
                    if i < split_data.shape[1]:
                        df[target_field] = split_data[i]
        elif operation == 'format':
            format_string = params.get('format', '{}')
            if field in df.columns:
                df[field] = df[field].apply(lambda x: format_string.format(x))
        else:
            raise ValueError(f"Unknown map operation: {operation}")
        
        return df
    
    def _apply_validation(self, df: pd.DataFrame, operation: str, field: str, params: Dict[str, Any]) -> pd.DataFrame:
        """Apply validation operations."""
        if field not in df.columns:
            logger.warning(f"Validation field '{field}' not found in data")
            return df
        
        if operation == 'required':
            # Remove rows with null/empty values
            initial_count = len(df)
            df = df.dropna(subset=[field])
            df = df[df[field].astype(str).str.strip() != '']
            removed = initial_count - len(df)
            if removed > 0:
                self.stats['validation_errors'] += removed
                logger.info(f"Validation 'required' on '{field}' removed {removed} records")
        elif operation == 'type':
            target_type = params.get('type', 'str')
            try:
                if target_type == 'int':
                    # Convert to numeric first, then round and convert to int
                    numeric_values = pd.to_numeric(df[field], errors='coerce')
                    df[field] = numeric_values.fillna(0).round().astype('int64')
                elif target_type == 'float':
                    df[field] = pd.to_numeric(df[field], errors='coerce')
                elif target_type == 'datetime':
                    df[field] = pd.to_datetime(df[field], errors='coerce')
                elif target_type == 'str':
                    df[field] = df[field].astype(str)
            except Exception as e:
                logger.warning(f"Type conversion failed for field '{field}': {e}")
        elif operation == 'pattern':
            pattern = params.get('pattern', '')
            if pattern:
                invalid_mask = ~df[field].astype(str).str.match(pattern, na=False)
                invalid_count = invalid_mask.sum()
                if invalid_count > 0:
                    self.stats['validation_errors'] += invalid_count
                    if self.error_handling == 'skip':
                        df = df[~invalid_mask]
                        logger.info(f"Pattern validation on '{field}' removed {invalid_count} records")
        
        return df
    
    def _apply_format(self, df: pd.DataFrame, operation: str, field: str, params: Dict[str, Any]) -> pd.DataFrame:
        """Apply formatting operations."""
        if field not in df.columns:
            logger.warning(f"Format field '{field}' not found in data")
            return df
        
        if operation == 'date':
            date_format = params.get('format', '%Y-%m-%d')
            try:
                df[field] = pd.to_datetime(df[field]).dt.strftime(date_format)
            except Exception as e:
                logger.warning(f"Date formatting failed for field '{field}': {e}")
        elif operation == 'number':
            decimal_places = params.get('decimal_places', 2)
            try:
                # Convert to numeric and round properly
                numeric_values = pd.to_numeric(df[field], errors='coerce')
                df[field] = numeric_values.round(decimal_places)
            except Exception as e:
                logger.warning(f"Number formatting failed for field '{field}': {e}")
        elif operation == 'text':
            case_type = params.get('case', 'lower')
            if case_type == 'upper':
                df[field] = df[field].astype(str).str.upper()
            elif case_type == 'lower':
                df[field] = df[field].astype(str).str.lower()
            elif case_type == 'title':
                df[field] = df[field].astype(str).str.title()
        elif operation == 'trim':
            df[field] = df[field].astype(str).str.strip()
        
        return df
    
    def _apply_aggregation(self, df: pd.DataFrame, operation: str, field: str, params: Dict[str, Any]) -> pd.DataFrame:
        """Apply aggregation operations."""
        if operation == 'group_by':
            group_fields = params.get('group_by', [])
            agg_functions = params.get('functions', {})
            if group_fields and agg_functions:
                grouped = df.groupby(group_fields).agg(agg_functions).reset_index()
                return grouped
        elif operation in ['count', 'sum', 'avg', 'min', 'max']:
            group_fields = params.get('group_by', [])
            if group_fields:
                if operation == 'count':
                    result = df.groupby(group_fields).size().reset_index(name=f'{field}_count')
                elif operation == 'sum':
                    result = df.groupby(group_fields)[field].sum().reset_index()
                elif operation == 'avg':
                    result = df.groupby(group_fields)[field].mean().reset_index()
                elif operation == 'min':
                    result = df.groupby(group_fields)[field].min().reset_index()
                elif operation == 'max':
                    result = df.groupby(group_fields)[field].max().reset_index()
                return result
        
        return df
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's configuration and input/output.
        
        Returns:
            A dictionary containing the JSON schema definition.
        """
        return {
            "node_type": "DataTransformNode",
            "description": "Transforms data through filtering, mapping, validation, and formatting",
            "config_schema": self.validator.get_schema('data_transform_node_config'),
            "supported_operations": self.SUPPORTED_OPERATIONS,
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
                        "description": "Data to transform (array of records or single record)"
                    }
                },
                "required": ["data"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Transformed data records"
                    },
                    "statistics": {
                        "type": "object",
                        "properties": {
                            "records_processed": {"type": "integer"},
                            "records_filtered": {"type": "integer"},
                            "validation_errors": {"type": "integer"},
                            "transformation_errors": {"type": "integer"}
                        }
                    },
                    "transformation_summary": {
                        "type": "object",
                        "properties": {
                            "initial_records": {"type": "integer"},
                            "final_records": {"type": "integer"},
                            "transformations_applied": {"type": "integer"},
                            "memory_used_mb": {"type": "number"}
                        }
                    }
                },
                "required": ["data", "statistics", "transformation_summary"]
            }
        }