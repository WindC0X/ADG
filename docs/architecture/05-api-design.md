## API Design Specification

### Overview

Based on the API design flaws identified in the architecture validation report, the ADG platform must establish a complete RESTful API specification. This includes an OpenAPI 3.0 specification definition, a versioning strategy, backward compatibility guarantees, and an automated documentation generation mechanism.

### RESTful API Design Principles

#### Core Design Principles

1.  **Resource-Oriented**: URLs represent resources, HTTP methods represent actions.
2.  **Stateless**: Each request contains all necessary information.
3.  **Uniform Interface**: Consistent URL structure and response format.
4.  **Layered System**: Clear architectural layers.
5.  **Cacheable**: Support for HTTP caching mechanisms.
6.  **Code-on-Demand**: Support for client-side extension (optional).

#### URL Design Specification

```yaml
# API URL Design Specification
url_design_patterns:
  # Resource collections
  collections: 
    pattern: "/api/v1/{resource}s"
    examples:
      - "GET /api/v1/directories"     # Get a list of directories
      - "POST /api/v1/workflows"      # Create a workflow
      - "GET /api/v1/users"           # Get a list of users
    
  # Individual resources
  resources:
    pattern: "/api/v1/{resource}s/{id}"
    examples:
      - "GET /api/v1/directories/123"     # Get a specific directory
      - "PUT /api/v1/workflows/456"       # Update a workflow
      - "DELETE /api/v1/users/789"        # Delete a user
    
  # Sub-resources
  sub_resources:
    pattern: "/api/v1/{resource}s/{id}/{sub_resource}s"
    examples:
      - "GET /api/v1/workflows/123/executions"     # Get workflow execution records
      - "POST /api/v1/directories/456/validate"    # Validate a directory
    
  # Action endpoints
  actions:
    pattern: "/api/v1/{resource}s/{id}/actions/{action}"
    examples:
      - "POST /api/v1/workflows/123/actions/execute"    # Execute a workflow
      - "POST /api/v1/directories/456/actions/export"   # Export a directory
    
  # Search and filtering
  search:
    pattern: "/api/v1/{resource}s?{filters}"
    examples:
      - "GET /api/v1/directories?status=completed&limit=20"
      - "GET /api/v1/workflows?created_after=2024-01-01"
```

### OpenAPI 3.0 Specification

#### API Specification Document Structure

```yaml
# openapi.yaml - ADG Platform API Specification (Enhanced with Unified Error Model & Pagination)
openapi: 3.0.3
info:
  title: ADG Intelligent Archive Directory Platform API
  description: |
    The ADG platform provides a complete API for archive directory generation and intelligent processing.
  
    ## Features
    - Archive directory generation and management
    - Intelligent workflow execution
    - AI/OCR document processing
    - User permission management
    - Real-time status monitoring
  
    ## Authentication Methods
    - JWT Token Authentication with JWKS support
    - API Key Authentication
    - Session Authentication
  
  version: "1.0.0"
  contact:
    name: ADG Development Team
    email: api-support@adg-platform.com
    url: https://docs.adg-platform.com
  license:
    name: MIT
    url: https://opensource.org/licenses/MIT
  
servers:
  - url: https://api.adg-platform.com/v1
    description: Production Environment
  - url: https://staging-api.adg-platform.com/v1
    description: Staging Environment
  - url: http://localhost:8000/v1
    description: Local Development Environment

# Global security configuration
security:
  - BearerAuth: []
  - ApiKeyAuth: []

# Enhanced Components with Unified Models
components:
  schemas:
    # Unified Error Response Model
    ErrorResponse:
      type: object
      required:
        - error
      properties:
        error:
          type: object
          required:
            - code
            - message
            - trace_id
            - timestamp
          properties:
            code:
              type: string
              description: Standardized error code
              examples: 
                - "VALIDATION_FAILED"
                - "RESOURCE_NOT_FOUND"
                - "AUTH_FAILED"
                - "RATE_LIMIT_EXCEEDED"
                - "INTERNAL_ERROR"
            message:
              type: string
              description: Human-readable error message
              examples:
                - "Validation failed for field 'name'"
                - "Directory not found"
                - "Authentication token expired"
            trace_id:
              type: string
              format: uuid
              description: Unique trace identifier for debugging
              example: "123e4567-e89b-12d3-a456-426614174000"
            timestamp:
              type: string
              format: date-time
              description: Error occurrence timestamp
              example: "2024-01-15T10:30:00Z"
            details:
              type: object
              additionalProperties: true
              description: Additional error context
              example:
                field: "name"
                provided_value: ""
                expected_format: "non-empty string"
    
    # Enhanced Pagination Model
    PaginationMetadata:
      type: object
      required:
        - total
        - page
        - page_size
        - total_pages
        - has_next
        - has_prev
      properties:
        total:
          type: integer
          minimum: 0
          description: Total number of items across all pages
          example: 150
        page:
          type: integer
          minimum: 1
          description: Current page number (1-based)
          example: 3
        page_size:
          type: integer
          minimum: 1
          maximum: 100
          description: Number of items per page
          example: 20
        total_pages:
          type: integer
          minimum: 0
          description: Total number of pages
          example: 8
        has_next:
          type: boolean
          description: Whether there are more pages after current
          example: true
        has_prev:
          type: boolean
          description: Whether there are pages before current
          example: true
        next_cursor:
          type: string
          nullable: true
          description: Cursor for next page (cursor-based pagination)
          example: "eyJpZCI6MTUwLCJjcmVhdGVkX2F0IjoiMjAyNC0wMS0xNVQxMDozMDowMFoifQ=="
        prev_cursor:
          type: string
          nullable: true
          description: Cursor for previous page (cursor-based pagination)
          example: "eyJpZCI6MTEwLCJjcmVhdGVkX2F0IjoiMjAyNC0wMS0xNFQxNToyMDowMFoifQ=="
    
    # Paginated Response Wrapper
    PaginatedResponse:
      type: object
      required:
        - data
        - pagination
        - meta
      properties:
        data:
          type: array
          items: {}
          description: Array of result items
        pagination:
          $ref: '#/components/schemas/PaginationMetadata'
        meta:
          $ref: '#/components/schemas/ResponseMeta'
    
    # Response Metadata
    ResponseMeta:
      type: object
      required:
        - trace_id
        - timestamp
        - api_version
      properties:
        trace_id:
          type: string
          format: uuid
          description: Request trace identifier
          example: "123e4567-e89b-12d3-a456-426614174000"
        timestamp:
          type: string
          format: date-time
          description: Response generation timestamp
          example: "2024-01-15T10:30:00Z"
        api_version:
          type: string
          description: API version used
          example: "1.0.0"
        processing_time_ms:
          type: number
          description: Server processing time in milliseconds
          example: 245.7
        rate_limit:
          type: object
          properties:
            limit:
              type: integer
              description: Rate limit per time window
              example: 1000
            remaining:
              type: integer
              description: Remaining requests in current window
              example: 847
            reset_at:
              type: string
              format: date-time
              description: When rate limit resets
              example: "2024-01-15T11:00:00Z"
    
    # Enhanced Directory Schema
    Directory:
      type: object
      required:
        - id
        - name
        - type
        - status
        - created_at
        - updated_at
      properties:
        id:
          type: string
          format: uuid
          description: Directory unique identifier
          example: "123e4567-e89b-12d3-a456-426614174000"
        name:
          type: string
          minLength: 1
          maxLength: 255
          description: Directory name
          example: "2024年档案目录"
        type:
          type: string
          enum: ["full_catalog", "volume_catalog", "file_catalog", "simplified"]
          description: Directory type
          example: "full_catalog"
        status:
          type: string
          enum: ["draft", "processing", "completed", "failed"]
          description: Directory generation status
          example: "completed"
        created_at:
          type: string
          format: date-time
          description: Creation timestamp
          example: "2024-01-15T10:30:00Z"
        updated_at:
          type: string
          format: date-time
          description: Last update timestamp
          example: "2024-01-15T12:45:00Z"
        created_by:
          type: string
          description: User ID who created the directory
          example: "user_123"
        file_count:
          type: integer
          minimum: 0
          description: Number of files in directory
          example: 1500
        size_bytes:
          type: integer
          minimum: 0
          description: Total size in bytes
          example: 256000000
        download_url:
          type: string
          format: uri
          nullable: true
          description: Download URL when completed
          example: "https://api.adg-platform.com/v1/directories/123e4567-e89b-12d3-a456-426614174000/download"
        progress:
          type: object
          properties:
            percentage:
              type: number
              minimum: 0
              maximum: 100
              description: Completion percentage
              example: 85.5
            current_step:
              type: string
              description: Current processing step
              example: "Generating Excel file"
            estimated_completion:
              type: string
              format: date-time
              nullable: true
              description: Estimated completion time
              example: "2024-01-15T13:15:00Z"
        trace_id:
          type: string
          format: uuid
          description: Creation trace identifier
          example: "123e4567-e89b-12d3-a456-426614174000"

  # Global Response Definitions
  responses:
    BadRequest:
      description: Bad Request - Invalid input parameters
      headers:
        X-Trace-ID:
          schema:
            type: string
            format: uuid
          description: Request trace identifier
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            error:
              code: "VALIDATION_FAILED"
              message: "Invalid input parameters"
              trace_id: "123e4567-e89b-12d3-a456-426614174000"
              timestamp: "2024-01-15T10:30:00Z"
              details:
                invalid_fields: ["name", "type"]
    
    Unauthorized:
      description: Unauthorized - Authentication required or invalid
      headers:
        X-Trace-ID:
          schema:
            type: string
            format: uuid
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            error:
              code: "AUTH_FAILED"
              message: "Authentication token expired"
              trace_id: "123e4567-e89b-12d3-a456-426614174000"
              timestamp: "2024-01-15T10:30:00Z"
              details:
                token_expired_at: "2024-01-15T10:15:00Z"
    
    NotFound:
      description: Not Found - Requested resource does not exist
      headers:
        X-Trace-ID:
          schema:
            type: string
            format: uuid
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            error:
              code: "RESOURCE_NOT_FOUND"
              message: "Directory not found"
              trace_id: "123e4567-e89b-12d3-a456-426614174000"
              timestamp: "2024-01-15T10:30:00Z"
              details:
                resource_type: "directory"
                resource_id: "123e4567-e89b-12d3-a456-426614174000"
    
    InternalError:
      description: Internal Server Error
      headers:
        X-Trace-ID:
          schema:
            type: string
            format: uuid
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            error:
              code: "INTERNAL_ERROR"
              message: "An unexpected error occurred"
              trace_id: "123e4567-e89b-12d3-a456-426614174000"
              timestamp: "2024-01-15T10:30:00Z"
              details:
                error_id: "ERR_20240115_103000_001"

  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: JWT access token with JWKS support
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: API key authentication

paths:
  # Enhanced Directory Management Endpoints
  /directories:
    get:
      summary: Get directory list with enhanced pagination
      description: Get a paginated list of archive directories with unified error handling and trace support
      tags: [Directory Management]
      parameters:
        - name: page
          in: query
          description: Page number (starts from 1)
          schema:
            type: integer
            minimum: 1
            default: 1
            example: 3
        - name: page_size
          in: query
          description: Number of items per page
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
            example: 20
        - name: cursor
          in: query
          description: Cursor for cursor-based pagination
          schema:
            type: string
            example: "eyJpZCI6MTUwLCJjcmVhdGVkX2F0IjoiMjAyNC0wMS0xNVQxMDozMDowMFoifQ=="
        - name: status
          in: query
          description: Filter by directory status
          schema:
            type: string
            enum: [draft, processing, completed, failed]
            example: "completed"
        - name: type
          in: query
          description: Filter by directory type
          schema:
            type: string
            enum: [full_catalog, volume_catalog, file_catalog, simplified]
            example: "full_catalog"
        - name: created_after
          in: query
          description: Filter by creation date (ISO 8601 format)
          schema:
            type: string
            format: date-time
            example: "2024-01-01T00:00:00Z"
      responses:
        '200':
          description: Successfully returns paginated list of directories
          headers:
            X-Trace-ID:
              schema:
                type: string
                format: uuid
              description: Request trace identifier
            X-Rate-Limit-Limit:
              schema:
                type: integer
              description: Rate limit per time window
            X-Rate-Limit-Remaining:
              schema:
                type: integer
              description: Remaining requests in current window
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/PaginatedResponse'
                  - type: object
                    properties:
                      data:
                        type: array
                        items:
                          $ref: '#/components/schemas/Directory'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '500':
          $ref: '#/components/responses/InternalError'
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '500':
          $ref: '#/components/responses/InternalServerError'
        
    post:
      summary: Create a new directory
      description: Create an archive directory generation task.
      tags: [Directory Management]
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateDirectoryRequest'
          multipart/form-data:
            schema:
              type: object
              properties:
                config:
                  $ref: '#/components/schemas/CreateDirectoryRequest'
                input_file:
                  type: string
                  format: binary
                  description: Input Excel file
                template_file:
                  type: string
                  format: binary
                  description: Template file (optional)
      responses:
        '201':
          description: Directory created successfully
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/Directory'
                  - type: object
                    properties:
                      meta:
                        $ref: '#/components/schemas/ResponseMeta'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '422':
          $ref: '#/components/responses/ValidationError'

  /directories/{directoryId}:
    parameters:
      - name: directoryId
        in: path
        required: true
        description: Unique identifier for the directory
        schema:
          type: string
          format: uuid
    get:
      summary: Get directory details
      description: Get detailed information for a specific directory.
      tags: [Directory Management]
      responses:
        '200':
          description: Successfully returns directory details
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/Directory'
                  - type: object
                    properties:
                      meta:
                        $ref: '#/components/schemas/ResponseMeta'
        '404':
          $ref: '#/components/responses/NotFound'
        
    put:
      summary: Update a directory
      description: Update the configuration information for a specific directory.
      tags: [Directory Management]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UpdateDirectoryRequest'
      responses:
        '200':
          description: Directory updated successfully
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/Directory'
                  - type: object
                    properties:
                      meta:
                        $ref: '#/components/schemas/ResponseMeta'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          $ref: '#/components/responses/ValidationError'
        
    delete:
      summary: Delete a directory
      description: Delete a specific directory (soft delete).
      tags: [Directory Management]
      responses:
        '204':
          description: Directory deleted successfully
        '404':
          $ref: '#/components/responses/NotFound'
        '409':
          description: Directory is currently being processed and cannot be deleted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /directories/{directoryId}/actions/execute:
    parameters:
      - name: directoryId
        in: path
        required: true
        schema:
          type: string
          format: uuid
    post:
      summary: Execute directory generation
      description: Start the directory generation processing task.
      tags: [Directory Management]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                height_method:
                  type: string
                  enum: [pillow, gdi, xlwings]
                  default: pillow
                  description: Row height calculation method
                priority:
                  type: string
                  enum: [low, normal, high]
                  default: normal
                  description: Task priority
      responses:
        '202':
          description: Task accepted and processing has begun
          content:
            application/json:
              schema:
                type: object
                properties:
                  task_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [accepted]
                  estimated_completion:
                    type: string
                    format: date-time
                  meta:
                    $ref: '#/components/schemas/ResponseMeta'

  # Workflow Management Endpoints
  /workflows:
    get:
      summary: Get workflow list
      tags: [Workflow Management]
      parameters:
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/LimitParam'
      responses:
        '200':
          description: Successfully returns a list of workflows
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Workflow'
                  pagination:
                    $ref: '#/components/schemas/Pagination'
                  
    post:
      summary: Create a workflow
      tags: [Workflow Management]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateWorkflowRequest'
      responses:
        '201':
          description: Workflow created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Workflow'

  # AI Processing Endpoints
  /ai/ocr:
    post:
      summary: OCR document recognition
      description: Use AI OCR to recognize document content.
      tags: [AI Processing]
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                image:
                  type: string
                  format: binary
                  description: Image file
                options:
                  type: object
                  properties:
                    engine:
                      type: string
                      enum: [umi-ocr, paddle-ocr, dots-ocr]
                      default: umi-ocr
                    language:
                      type: string
                      enum: [zh-CN, en, auto]
                      default: zh-CN
                    output_format:
                      type: string
                      enum: [text, json, pdf]
                      default: json
              required:
                - image
      responses:
        '200':
          description: OCR recognition successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  text:
                    type: string
                    description: Recognized text
                  confidence:
                    type: number
                    format: float
                    minimum: 0
                    maximum: 1
                    description: Recognition confidence score
                  regions:
                    type: array
                    items:
                      $ref: '#/components/schemas/OCRRegion'
                  processing_time:
                    type: number
                    format: float
                    description: Processing time (seconds)
                  meta:
                    $ref: '#/components/schemas/ResponseMeta'
        '400':
          $ref: '#/components/responses/BadRequest'
        '413':
          description: Payload too large
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  # System Management Endpoints
  /system/health:
    get:
      summary: System health check
      description: Get the system's health status.
      tags: [System Management]
      security: []  # No authentication required
      responses:
        '200':
          description: System health status
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [healthy, degraded, unhealthy]
                  timestamp:
                    type: string
                    format: date-time
                  version:
                    type: string
                  services:
                    type: object
                    properties:
                      database:
                        $ref: '#/components/schemas/ServiceHealth'
                      ai_services:
                        $ref: '#/components/schemas/ServiceHealth'
                      file_storage:
                        $ref: '#/components/schemas/ServiceHealth'
                  metrics:
                    type: object
                    properties:
                      memory_usage:
                        type: number
                        format: float
                        description: Memory usage ratio (0-1)
                      cpu_usage:
                        type: number
                        format: float
                        description: CPU usage ratio (0-1)
                      active_tasks:
                        type: integer
                        description: Number of active tasks

# Data model definitions
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key

  parameters:
    PageParam:
      name: page
      in: query
      description: Page number
      schema:
        type: integer
        minimum: 1
        default: 1
    LimitParam:
      name: limit
      in: query
      description: Items per page
      schema:
        type: integer
        minimum: 1
        maximum: 100
        default: 20

  schemas:
    # Core business models
    Directory:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: Unique directory identifier
        name:
          type: string
          maxLength: 255
          description: Directory name
        description:
          type: string
          maxLength: 1000
          description: Directory description
        type:
          type: string
          enum: [CollectionDirectory, FileUnitDirectory, InFileDirectory, SimplifiedDirectory]
          description: Directory type
        status:
          type: string
          enum: [draft, processing, completed, failed]
          description: Processing status
        config:
          $ref: '#/components/schemas/DirectoryConfig'
        metadata:
          type: object
          description: Metadata information
        statistics:
          $ref: '#/components/schemas/DirectoryStatistics'
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        created_by:
          type: string
          format: uuid
          description: User ID of the creator
      required:
        - id
        - name
        - type
        - status
        - created_at

    DirectoryConfig:
      type: object
      properties:
        template_file:
          type: string
          description: Path to the template file
        height_method:
          type: string
          enum: [pillow, gdi, xlwings]
          default: pillow
        page_orientation:
          type: string
          enum: [portrait, landscape]
          default: landscape
        font_settings:
          type: object
          properties:
            name:
              type: string
              default: SimSun
            size:
              type: integer
              minimum: 8
              maximum: 72
              default: 11
        pagination:
          type: object
          properties:
            rows_per_page:
              type: integer
              minimum: 1
              default: 50
            auto_page_break:
              type: boolean
              default: true

    DirectoryStatistics:
      type: object
      properties:
        total_records:
          type: integer
          minimum: 0
        total_pages:
          type: integer
          minimum: 0
        processing_time:
          type: number
          format: float
          description: Processing time (seconds)
        file_size:
          type: integer
          description: Output file size (bytes)

    Workflow:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
          maxLength: 255
        description:
          type: string
          maxLength: 1000
        definition:
          type: object
          description: Workflow definition (DAG structure)
        status:
          type: string
          enum: [active, inactive, deprecated]
        version:
          type: string
          pattern: '^v\d+\.\d+\.\d+$'
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    OCRRegion:
      type: object
      properties:
        text:
          type: string
        confidence:
          type: number
          format: float
          minimum: 0
          maximum: 1
        bbox:
          type: array
          items:
            type: number
          minItems: 4
          maxItems: 4
          description: Bounding box coordinates [x1, y1, x2, y2]

    ServiceHealth:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, unhealthy, unknown]
        last_check:
          type: string
          format: date-time
        response_time:
          type: number
          format: float
          description: Response time (milliseconds)

    # Request models
    CreateDirectoryRequest:
      type: object
      properties:
        name:
          type: string
          maxLength: 255
        description:
          type: string
          maxLength: 1000
        type:
          type: string
          enum: [CollectionDirectory, FileUnitDirectory, InFileDirectory, SimplifiedDirectory]
        config:
          $ref: '#/components/schemas/DirectoryConfig'
      required:
        - name
        - type

    UpdateDirectoryRequest:
      type: object
      properties:
        name:
          type: string
          maxLength: 255
        description:
          type: string
          maxLength: 1000
        config:
          $ref: '#/components/schemas/DirectoryConfig'

    CreateWorkflowRequest:
      type: object
      properties:
        name:
          type: string
          maxLength: 255
        description:
          type: string
          maxLength: 1000
        definition:
          type: object
      required:
        - name
        - definition

    # Response models
    Pagination:
      type: object
      properties:
        current_page:
          type: integer
          minimum: 1
        per_page:
          type: integer
          minimum: 1
        total_pages:
          type: integer
          minimum: 0
        total_items:
          type: integer
          minimum: 0
        has_next:
          type: boolean
        has_prev:
          type: boolean

    ResponseMeta:
      type: object
      properties:
        request_id:
          type: string
          format: uuid
        timestamp:
          type: string
          format: date-time
        api_version:
          type: string
        rate_limit:
          type: object
          properties:
            limit:
              type: integer
            remaining:
              type: integer
            reset:
              type: string
              format: date-time

    Error:
      type: object
      properties:
        error:
          type: object
          properties:
            code:
              type: string
            message:
              type: string
            details:
              type: object
            request_id:
              type: string
              format: uuid
        meta:
          $ref: '#/components/schemas/ResponseMeta'
      required:
        - error

    ValidationError:
      allOf:
        - $ref: '#/components/schemas/Error'
        - type: object
          properties:
            error:
              type: object
              properties:
                validation_errors:
                  type: array
                  items:
                    type: object
                    properties:
                      field:
                        type: string
                      message:
                        type: string
                      code:
                        type: string

  # Standard responses
  responses:
    BadRequest:
      description: Bad request parameters
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    Unauthorized:
      description: Unauthorized
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    Forbidden:
      description: Insufficient permissions
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    ValidationError:
      description: Data validation failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ValidationError'
    InternalServerError:
      description: Internal server error
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'

# API Tags
tags:
  - name: Directory Management
    description: Archive directory generation and management
  - name: Workflow Management
    description: Intelligent workflow definition and execution
  - name: AI Processing
    description: AI/OCR document processing services
  - name: User Management
    description: User account and permission management
  - name: System Management
    description: System monitoring and configuration management
```

### API Versioning Strategy

#### Versioning Scheme

```python
# api/versioning.py
"""
API versioning strategy implementation.
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, date


class VersionStrategy(Enum):
    """Versioning strategies"""
    URL_PATH = "url_path"          # /api/v1/resource
    HEADER = "header"              # Accept: application/vnd.api+json;version=1
    QUERY_PARAM = "query_param"    # /api/resource?version=1


@dataclass
class APIVersion:
    """API version information"""
    version: str                   # "1.0", "1.1", "2.0"
    status: str                   # "current", "deprecated", "sunset"
    release_date: date
    sunset_date: Optional[date] = None
    breaking_changes: List[str] = None
    migration_guide: Optional[str] = None


class VersionManager:
    """Version manager"""
  
    def __init__(self):
        self.versions = {
            "1.0": APIVersion(
                version="1.0",
                status="current",
                release_date=date(2025, 8, 17),
                breaking_changes=[],
                migration_guide="Initial version"
            ),
            "1.1": APIVersion(
                version="1.1", 
                status="current",
                release_date=date(2025, 10, 1),
                breaking_changes=[
                    "Added new authentication header requirements",
                    "Renamed some response fields"
                ],
                migration_guide="https://docs.adg-platform.com/migration/v1.0-to-v1.1"
            ),
            "2.0": APIVersion(
                version="2.0",
                status="beta",
                release_date=date(2025, 12, 1),
                breaking_changes=[
                    "Refactored all endpoint URL structures",
                    "Unified error response format",
                    "Removed deprecated fields"
                ],
                migration_guide="https://docs.adg-platform.com/migration/v1.x-to-v2.0"
            )
        }
        self.current_version = "1.0"
        self.default_strategy = VersionStrategy.URL_PATH
      
    def get_supported_versions(self) -> List[str]:
        """Get the list of supported versions"""
        return [v for v, info in self.versions.items() 
                if info.status in ["current", "beta"]]
      
    def is_version_supported(self, version: str) -> bool:
        """Check if a version is supported"""
        return version in self.get_supported_versions()
      
    def get_deprecation_info(self, version: str) -> Optional[Dict]:
        """Get version deprecation information"""
        version_info = self.versions.get(version)
        if not version_info or version_info.status != "deprecated":
            return None
          
        return {
            "version": version,
            "sunset_date": version_info.sunset_date.isoformat() if version_info.sunset_date else None,
            "migration_guide": version_info.migration_guide,
            "breaking_changes": version_info.breaking_changes
        }


class BackwardCompatibilityManager:
    """Backward compatibility manager"""
  
    def __init__(self):
        self.field_mappings = self._init_field_mappings()
        self.deprecated_endpoints = self._init_deprecated_endpoints()
      
    def _init_field_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize field mappings"""
        return {
            "1.0_to_1.1": {
                # v1.0 field -> v1.1 field
                "directory_id": "id",
                "creation_time": "created_at",
                "modification_time": "updated_at",
                "record_count": "total_records"
            },
            "1.1_to_2.0": {
                # v1.1 field -> v2.0 field
                "config.template_path": "config.template_file",
                "statistics.pages": "statistics.total_pages",
                "user_id": "created_by"
            }
        }
      
    def _init_deprecated_endpoints(self) -> Dict[str, Dict]:
        """Initialize deprecated endpoint mappings"""
        return {
            "GET /api/v1/archive-directories": {
                "replacement": "GET /api/v1/directories",
                "deprecated_in": "1.1",
                "sunset_in": "2.0",
                "message": "Please use the new /directories endpoint"
            },
            "POST /api/v1/generate-directory": {
                "replacement": "POST /api/v1/directories/{id}/actions/execute",
                "deprecated_in": "1.1", 
                "sunset_in": "2.0",
                "message": "Please use the new execution action endpoint"
            }
        }
      
    def transform_response(self, data: Dict, from_version: str, to_version: str) -> Dict:
        """Transform response data format"""
        mapping_key = f"{from_version}_to_{to_version}"
        mappings = self.field_mappings.get(mapping_key, {})
      
        if not mappings:
            return data
          
        transformed = data.copy()
      
        # Field renaming
        for old_field, new_field in mappings.items():
            if old_field in transformed:
                transformed[new_field] = transformed.pop(old_field)
              
        return transformed
      
    def add_deprecation_warnings(self, response_headers: Dict, endpoint: str, version: str):
        """Add deprecation warning headers"""
        deprecation_info = self.deprecated_endpoints.get(endpoint)
      
        if deprecation_info:
            response_headers.update({
                "Deprecation": f"version=\"{deprecation_info['deprecated_in']}\"",
                "Sunset": deprecation_info.get('sunset_in', ''),
                "Link": f"<{deprecation_info['replacement']}>; rel=\"successor-version\"",
                "Warning": f"299 - \"{deprecation_info['message']}\""
            })
```

### Automated Documentation Generation

#### Documentation Generation Toolchain

```python
# scripts/generate_docs.py
"""
Automated API documentation generation script.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any
import subprocess


class APIDocGenerator:
    """API documentation generator"""
  
    def __init__(self, openapi_file: str = "openapi.yaml"):
        self.openapi_file = Path(openapi_file)
        self.output_dir = Path("docs/api")
      
    def generate_all_docs(self):
        """Generate all formats of documentation"""
        self.ensure_output_directory()
      
        # Generate HTML documentation
        self.generate_html_docs()
      
        # Generate Markdown documentation
        self.generate_markdown_docs()
      
        # Generate Postman collection
        self.generate_postman_collection()
      
        # Generate SDK examples
        self.generate_sdk_examples()
      
    def ensure_output_directory(self):
        """Ensure the output directory exists"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
      
    def generate_html_docs(self):
        """Generate interactive HTML documentation"""
        # Use Redoc to generate HTML docs
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>ADG Platform API Documentation</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; }}
    </style>
</head>
<body>
    <redoc spec-url="{spec_url}"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
</body>
</html>
        """
      
        # Copy the OpenAPI specification file
        spec_file = self.output_dir / "openapi.yaml"
        with open(self.openapi_file) as src, open(spec_file, 'w') as dst:
            dst.write(src.read())
          
        # Generate the HTML file
        html_file = self.output_dir / "index.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_template.format(spec_url="./openapi.yaml"))
          
    def generate_markdown_docs(self):
        """Generate Markdown documentation"""
        try:
            # Use widdershins to generate Markdown
            subprocess.run([
                "widdershins",
                str(self.openapi_file),
                "-o", str(self.output_dir / "api.md"),
                "--language_tabs", "python:Python", "javascript:JavaScript", "curl:cURL"
            ], check=True)
        except subprocess.CalledProcessError:
            print("Warning: widdershins not installed, skipping Markdown documentation generation.")
          
    def generate_postman_collection(self):
        """Generate a Postman collection"""
        try:
            # Use openapi-to-postman for conversion
            subprocess.run([
                "openapi2postman",
                "-s", str(self.openapi_file),
                "-o", str(self.output_dir / "adg-api.postman_collection.json"),
                "-p"
            ], check=True)
        except subprocess.CalledProcessError:
            print("Warning: openapi2postman not installed, skipping Postman collection generation.")
          
    def generate_sdk_examples(self):
        """Generate SDK usage examples"""
        examples = {
            "python": self._generate_python_examples(),
            "javascript": self._generate_javascript_examples(),
            "curl": self._generate_curl_examples()
        }
      
        for language, code in examples.items():
            example_file = self.output_dir / f"examples_{language}.md"
            with open(example_file, 'w', encoding='utf-8') as f:
                f.write(f"# ADG API {language.title()} Examples\n\n")
                f.write(code)
              
    def _generate_python_examples(self) -> str:
        """Generate Python SDK examples"""
        return """
## Python SDK Example

### Installation
```bash
pip install adg-platform-sdk
```

### Authentication
```python
from adg_platform import ADGClient

# Using JWT token
client = ADGClient(
    base_url="https://api.adg-platform.com",
    auth_token="your_jwt_token"
)

# Using API Key
client = ADGClient(
    base_url="https://api.adg-platform.com", 
    api_key="your_api_key"
)
```

### Create a Directory
```python
# Create a new directory
directory = client.directories.create(
    name="Test Directory",
    type="CollectionDirectory",
    config={
        "height_method": "pillow",
        "page_orientation": "landscape"
    }
)

print(f"Directory created: {directory.id}")
```

### Execute Directory Generation
```python
# Upload a file and execute generation
with open("input.xlsx", "rb") as f:
    result = client.directories.execute(
        directory.id,
        input_file=f,
        height_method="pillow"
    )

print(f"Task ID: {result.task_id}")

# Monitor task status
status = client.tasks.get_status(result.task_id)
while status.status == "processing":
    time.sleep(5)
    status = client.tasks.get_status(result.task_id)

print(f"Task completed: {status.status}")
```

### OCR Document Recognition
```python
# OCR image recognition
with open("document.jpg", "rb") as f:
    result = client.ai.ocr(
        image=f,
        engine="umi-ocr",
        language="zh-CN"
    )

print(f"Recognized text: {result.text}")
print(f"Confidence: {result.confidence}")
```
        """
      
    def _generate_javascript_examples(self) -> str:
        """Generate JavaScript SDK examples"""
        return """
## JavaScript SDK Example

### Installation
```bash
npm install @adg-platform/sdk
```

### Authentication
```javascript
import { ADGClient } from '@adg-platform/sdk';

const client = new ADGClient({
    baseURL: 'https://api.adg-platform.com',
    authToken: 'your_jwt_token'
});
```

### Create a Directory
```javascript
// Create a new directory
const directory = await client.directories.create({
    name: 'Test Directory',
    type: 'CollectionDirectory',
    config: {
        height_method: 'pillow',
        page_orientation: 'landscape'
    }
});

console.log(`Directory created: ${directory.id}`);
```

### File Upload and Processing
```javascript
// Upload a file
const formData = new FormData();
formData.append('input_file', fileInput.files[0]);
formData.append('config', JSON.stringify({
    height_method: 'pillow'
}));

const result = await client.directories.execute(directory.id, formData);
console.log(`Task ID: ${result.task_id}`);
```
        """
      
    def _generate_curl_examples(self) -> str:
        """Generate cURL examples"""
        return """
## cURL Example

### Authentication
```bash
# Set authentication token
export ADG_TOKEN="your_jwt_token"
export API_BASE="https://api.adg-platform.com/v1"
```

### Get Directory List
```bash
curl -X GET "$API_BASE/directories" \\
  -H "Authorization: Bearer $ADG_TOKEN" \\
  -H "Content-Type: application/json"
```

### Create a Directory
```bash
curl -X POST "$API_BASE/directories" \\
  -H "Authorization: Bearer $ADG_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Test Directory",
    "type": "CollectionDirectory",
    "config": {
      "height_method": "pillow",
      "page_orientation": "landscape"
    }
  }'
```

### Upload File and Execute
```bash
curl -X POST "$API_BASE/directories/{directory_id}/actions/execute" \\
  -H "Authorization: Bearer $ADG_TOKEN" \\
  -F "input_file=@input.xlsx" \\
  -F 'config={"height_method": "pillow"}'
```

### OCR Image Recognition
```bash
curl -X POST "$API_BASE/ai/ocr" \\
  -H "Authorization: Bearer $ADG_TOKEN" \\
  -F "image=@document.jpg" \\
  -F 'options={"engine": "umi-ocr", "language": "zh-CN"}'
```
        """


class DocumentationValidator:
    """Documentation validator"""
  
    def __init__(self, openapi_file: str):
        self.openapi_file = openapi_file
      
    def validate_openapi_spec(self) -> Dict[str, Any]:
        """Validate the OpenAPI specification"""
        try:
            # Use swagger-codegen to validate
            result = subprocess.run([
                "swagger-codegen-cli", "validate",
                "-i", self.openapi_file
            ], capture_output=True, text=True)
          
            return {
                "valid": result.returncode == 0,
                "errors": result.stderr if result.returncode != 0 else None,
                "warnings": result.stdout
            }
        except FileNotFoundError:
            return {
                "valid": False,
                "errors": "swagger-codegen-cli not found",
                "warnings": None
            }
          
    def check_breaking_changes(self, old_spec: str, new_spec: str) -> List[Dict]:
        """Check for breaking changes"""
        try:
            # Use openapi-diff to check changes
            result = subprocess.run([
                "openapi-diff", old_spec, new_spec,
                "--fail-on-incompatible"
            ], capture_output=True, text=True)
          
            if result.returncode != 0:
                return [{"type": "breaking_change", "message": result.stdout}]
            return []
        except FileNotFoundError:
            return [{"type": "error", "message": "openapi-diff not found"}]


if __name__ == "__main__":
    # Generate documentation
    generator = APIDocGenerator()
    generator.generate_all_docs()
  
    # Validate specification
    validator = DocumentationValidator("openapi.yaml")
    validation_result = validator.validate_openapi_spec()
  
    if validation_result["valid"]:
        print("✅ OpenAPI specification validated successfully.")
    else:
        print(f"❌ OpenAPI specification validation failed: {validation_result['errors']}")
      
    print("📚 API documentation generation complete.")
```

