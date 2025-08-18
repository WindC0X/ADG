"""
JSON Schema definitions for data validation.

This module provides JSON Schema validation for all core data models,
ensuring data integrity throughout the node execution pipeline.
"""

import json
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError, Draft7Validator
import logging

logger = logging.getLogger(__name__)


# Core data model schemas
ARCHIVE_DOCUMENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ArchiveDocument",
    "description": "Schema for archive document data model",
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "minLength": 1,
            "description": "Unique identifier for the document"
        },
        "title": {
            "type": "string",
            "minLength": 1,
            "description": "Title of the document"
        },
        "file_path": {
            "type": ["string", "null"],
            "description": "Path to the document file"
        },
        "metadata": {
            "type": "object",
            "additionalProperties": True,
            "description": "Additional metadata for the document"
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
            "description": "Creation timestamp in ISO format"
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of tags associated with the document"
        },
        "content": {
            "type": ["string", "null"],
            "description": "Document content"
        }
    },
    "required": ["id", "title", "created_at"],
    "additionalProperties": False
}

DIRECTORY_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "DirectoryConfig",
    "description": "Schema for directory generation configuration",
    "type": "object",
    "properties": {
        "template_path": {
            "type": "string",
            "minLength": 1,
            "description": "Path to the Excel template file"
        },
        "output_path": {
            "type": "string",
            "minLength": 1,
            "description": "Output directory path"
        },
        "directory_type": {
            "type": "string",
            "enum": ["卷内目录", "案卷目录", "全引目录", "简化目录"],
            "description": "Type of directory to generate"
        },
        "column_mappings": {
            "type": "object",
            "additionalProperties": {
                "type": "string"
            },
            "description": "Mapping of data fields to Excel columns"
        },
        "page_settings": {
            "type": "object",
            "properties": {
                "orientation": {
                    "type": "string",
                    "enum": ["portrait", "landscape"]
                },
                "margin_top": {"type": "number", "minimum": 0},
                "margin_bottom": {"type": "number", "minimum": 0},
                "margin_left": {"type": "number", "minimum": 0},
                "margin_right": {"type": "number", "minimum": 0}
            },
            "additionalProperties": True,
            "description": "Page layout settings"
        },
        "height_calculation_method": {
            "type": "string",
            "enum": ["xlwings", "gdi", "pillow"],
            "default": "pillow",
            "description": "Method for calculating row heights"
        },
        "auto_fit_columns": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of columns to auto-fit"
        },
        "validation_rules": {
            "type": "object",
            "additionalProperties": True,
            "description": "Data validation rules"
        }
    },
    "required": ["template_path", "output_path", "directory_type"],
    "additionalProperties": False
}

WORKFLOW_CONTEXT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "WorkflowContext",
    "description": "Schema for workflow execution context",
    "type": "object",
    "properties": {
        "workflow_id": {
            "type": "string",
            "minLength": 1,
            "description": "Unique workflow identifier"
        },
        "current_node_id": {
            "type": ["string", "null"],
            "description": "Currently executing node ID"
        },
        "execution_state": {
            "type": "object",
            "additionalProperties": True,
            "description": "Current execution state data"
        },
        "shared_data": {
            "type": "object",
            "additionalProperties": True,
            "description": "Data shared between nodes"
        },
        "started_at": {
            "type": "string",
            "format": "date-time",
            "description": "Workflow start timestamp"
        },
        "completed_at": {
            "type": ["string", "null"],
            "format": "date-time",
            "description": "Workflow completion timestamp"
        },
        "status": {
            "type": "string",
            "enum": ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
            "description": "Current workflow status"
        }
    },
    "required": ["workflow_id", "started_at", "status"],
    "additionalProperties": False
}

NODE_INPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "NodeInput",
    "description": "Schema for node input data",
    "type": "object",
    "properties": {
        "data": {
            "type": "object",
            "additionalProperties": True,
            "description": "Input data payload"
        },
        "metadata": {
            "type": "object",
            "additionalProperties": True,
            "description": "Input metadata"
        },
        "node_id": {
            "type": ["string", "null"],
            "description": "Source node identifier"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "Input creation timestamp"
        }
    },
    "required": ["data", "timestamp"],
    "additionalProperties": False
}

NODE_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "NodeOutput",
    "description": "Schema for node output data",
    "type": "object",
    "properties": {
        "data": {
            "type": "object",
            "additionalProperties": True,
            "description": "Output data payload"
        },
        "metadata": {
            "type": "object",
            "additionalProperties": True,
            "description": "Output metadata"
        },
        "node_id": {
            "type": ["string", "null"],
            "description": "Producing node identifier"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "Output creation timestamp"
        },
        "status": {
            "type": "string",
            "enum": ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
            "description": "Processing status"
        },
        "processing_time_ms": {
            "type": ["number", "null"],
            "minimum": 0,
            "description": "Processing time in milliseconds"
        },
        "errors": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of error messages"
        },
        "warnings": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of warning messages"
        }
    },
    "required": ["data", "timestamp", "status"],
    "additionalProperties": False
}

# Node type specific schemas
FILE_INPUT_NODE_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FileInputNodeConfig",
    "description": "Configuration schema for file input nodes",
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "minLength": 1,
            "description": "Path to the input file"
        },
        "file_type": {
            "type": "string",
            "enum": ["excel", "csv", "json"],
            "description": "Type of file to read"
        },
        "encoding": {
            "type": "string",
            "default": "utf-8",
            "description": "File encoding"
        },
        "sheet_name": {
            "type": ["string", "number", "null"],
            "description": "Excel sheet name or index (for Excel files)"
        },
        "skip_rows": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "Number of rows to skip from the beginning"
        },
        "max_rows": {
            "type": ["integer", "null"],
            "minimum": 1,
            "description": "Maximum number of rows to read"
        },
        "column_mappings": {
            "type": "object",
            "additionalProperties": {
                "type": "string"
            },
            "description": "Column name mappings"
        }
    },
    "required": ["file_path", "file_type"],
    "additionalProperties": False
}

DATA_TRANSFORM_NODE_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "DataTransformNodeConfig",
    "description": "Configuration schema for data transformation nodes",
    "type": "object",
    "properties": {
        "transformations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["filter", "map", "validate", "format", "aggregate"]
                    },
                    "field": {
                        "type": "string",
                        "description": "Target field name"
                    },
                    "operation": {
                        "type": "string",
                        "description": "Transformation operation"
                    },
                    "parameters": {
                        "type": "object",
                        "additionalProperties": True,
                        "description": "Operation parameters"
                    }
                },
                "required": ["type", "operation"]
            },
            "description": "List of transformations to apply"
        },
        "validation_rules": {
            "type": "object",
            "additionalProperties": True,
            "description": "Data validation rules"
        },
        "error_handling": {
            "type": "string",
            "enum": ["strict", "skip", "default"],
            "default": "strict",
            "description": "Error handling strategy"
        }
    },
    "required": ["transformations"],
    "additionalProperties": False
}

FILE_OUTPUT_NODE_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FileOutputNodeConfig",
    "description": "Configuration schema for file output nodes",
    "type": "object",
    "properties": {
        "output_path": {
            "type": "string",
            "minLength": 1,
            "description": "Output file path"
        },
        "template_path": {
            "type": ["string", "null"],
            "description": "Template file path (for Excel generation)"
        },
        "format": {
            "type": "string",
            "enum": ["excel", "csv", "json"],
            "description": "Output format"
        },
        "overwrite": {
            "type": "boolean",
            "default": False,
            "description": "Whether to overwrite existing files"
        },
        "excel_options": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "start_row": {"type": "integer", "minimum": 1},
                "start_col": {"type": "integer", "minimum": 1},
                "auto_fit": {"type": "boolean", "default": True},
                "page_setup": {
                    "type": "object",
                    "properties": {
                        "orientation": {"type": "string", "enum": ["portrait", "landscape"]},
                        "paper_size": {"type": "integer"},
                        "margins": {
                            "type": "object",
                            "properties": {
                                "top": {"type": "number"},
                                "bottom": {"type": "number"},
                                "left": {"type": "number"},
                                "right": {"type": "number"}
                            }
                        }
                    }
                }
            },
            "description": "Excel-specific output options"
        }
    },
    "required": ["output_path", "format"],
    "additionalProperties": False
}


class SchemaValidator:
    """
    JSON Schema validator for ADG data models.
    
    Provides centralized validation for all data structures used in the platform.
    """
    
    def __init__(self):
        """Initialize the schema validator with all schemas."""
        self.schemas = {
            'archive_document': ARCHIVE_DOCUMENT_SCHEMA,
            'directory_config': DIRECTORY_CONFIG_SCHEMA,
            'workflow_context': WORKFLOW_CONTEXT_SCHEMA,
            'node_input': NODE_INPUT_SCHEMA,
            'node_output': NODE_OUTPUT_SCHEMA,
            'file_input_node_config': FILE_INPUT_NODE_CONFIG_SCHEMA,
            'data_transform_node_config': DATA_TRANSFORM_NODE_CONFIG_SCHEMA,
            'file_output_node_config': FILE_OUTPUT_NODE_CONFIG_SCHEMA
        }
        
        # Pre-compile validators for better performance
        self.validators = {
            name: Draft7Validator(schema) 
            for name, schema in self.schemas.items()
        }
    
    def validate_data(self, data: Dict[str, Any], schema_name: str) -> List[str]:
        """
        Validate data against a specific schema.
        
        Args:
            data: Data to validate.
            schema_name: Name of the schema to validate against.
            
        Returns:
            List of validation error messages (empty if valid).
        """
        if schema_name not in self.validators:
            raise ValueError(f"Unknown schema: {schema_name}")
        
        validator = self.validators[schema_name]
        errors = []
        
        for error in validator.iter_errors(data):
            error_path = " -> ".join(str(p) for p in error.absolute_path)
            if error_path:
                error_msg = f"Field '{error_path}': {error.message}"
            else:
                error_msg = error.message
            errors.append(error_msg)
        
        return errors
    
    def is_valid(self, data: Dict[str, Any], schema_name: str) -> bool:
        """
        Check if data is valid against a schema.
        
        Args:
            data: Data to validate.
            schema_name: Name of the schema to validate against.
            
        Returns:
            True if data is valid, False otherwise.
        """
        return len(self.validate_data(data, schema_name)) == 0
    
    def validate_archive_document(self, data: Dict[str, Any]) -> List[str]:
        """Validate ArchiveDocument data."""
        return self.validate_data(data, 'archive_document')
    
    def validate_directory_config(self, data: Dict[str, Any]) -> List[str]:
        """Validate DirectoryConfig data."""
        return self.validate_data(data, 'directory_config')
    
    def validate_workflow_context(self, data: Dict[str, Any]) -> List[str]:
        """Validate WorkflowContext data."""
        return self.validate_data(data, 'workflow_context')
    
    def validate_node_input(self, data: Dict[str, Any]) -> List[str]:
        """Validate NodeInput data."""
        return self.validate_data(data, 'node_input')
    
    def validate_node_output(self, data: Dict[str, Any]) -> List[str]:
        """Validate NodeOutput data."""
        return self.validate_data(data, 'node_output')
    
    def validate_node_config(self, data: Dict[str, Any], node_type: str) -> List[str]:
        """
        Validate node configuration data.
        
        Args:
            data: Configuration data to validate.
            node_type: Type of node ('file_input', 'data_transform', 'file_output').
            
        Returns:
            List of validation error messages.
        """
        schema_name = f"{node_type}_node_config"
        return self.validate_data(data, schema_name)
    
    def get_schema(self, schema_name: str) -> Dict[str, Any]:
        """Get a schema by name."""
        if schema_name not in self.schemas:
            raise ValueError(f"Unknown schema: {schema_name}")
        return self.schemas[schema_name].copy()
    
    def list_schemas(self) -> List[str]:
        """Get list of available schema names."""
        return list(self.schemas.keys())


# Global validator instance
_validator: Optional[SchemaValidator] = None


def get_validator() -> SchemaValidator:
    """Get the global schema validator instance."""
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator


def validate_data(data: Dict[str, Any], schema_name: str) -> List[str]:
    """Convenience function to validate data."""
    return get_validator().validate_data(data, schema_name)


def is_valid_data(data: Dict[str, Any], schema_name: str) -> bool:
    """Convenience function to check if data is valid."""
    return get_validator().is_valid(data, schema_name)