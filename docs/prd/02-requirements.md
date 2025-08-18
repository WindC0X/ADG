# 功能需求

### Functional Requirements

**FR1**: **Platform Refactoring** - Refactor ADG into an extensible platform supporting the archive digitization process, using an atomic node architecture for flexible workflow configuration.

**FR2**: **Node-based Workflow Engine** - Build a lightweight, DAG-based node execution engine that supports flexible composition and visual configuration of data I/O nodes, processing nodes, and trigger nodes.

**FR3**: **Progressive Intelligent Validation** - Start with traditional rule-based validation and progressively integrate LLM capabilities to achieve intelligent quality checks and anomaly detection for archive data.

**FR4**: **Intelligent Directory Entry Assistance** - Implement a two-tier LLM strategy: **常驻 Hunyuan-1.8B/4B(INT4) 或 Qwen3-4B-Instruct(INT4) 作为默认模型，7B(INT4) 按需加载并空闲卸载**。Integrate UMI-OCR for OCR recognition of archive images, automatic metadata extraction, and intelligent suggestions for directory information. Trigger 7B model loading when confidence score < 0.85 or complexity threshold exceeded (mixed languages, formulas, complex tables). Auto-unload 7B model after 10 minutes of idle time to free resources.

**FR5**: **Multi-stage Process Integration** - Expand existing functionality to cover multiple stages of the digitization process, including entry, validation, conversion, and printing, establishing data flow between stages.

**FR6**: **Batch Processing Optimization** - Refactor the current processing model to support parallel processing of large batches of archives, along with progress management and optimized resource scheduling.

**FR7**: **Standardized API Interface** - Design RESTful API interfaces to support data exchange with existing archive processing systems, adhering to archival industry standards.

**FR8**: **Configuration-Driven Architecture** - Support workflow definition via JSON/YAML configuration to reduce custom development costs and improve business adaptability.

**FR9**: **Manual Intervention Mechanism** - Support manual review and confirmation at critical nodes to ensure the accuracy and controllability of archive processing.

**FR10**: **Enhanced Error Handling** - Establish a comprehensive exception handling and recovery mechanism, supporting workflow breakpoint resumption and error rollback.

### Non-Functional Requirements (Revised)

**NFR1**: **Hardware Optimization** - The system must run stably in an i5-9400 + 8GB RAM environment, strictly adhering to the memory budget allocation.

**NFR2**: **Layered Performance Requirements** (Redline Revision)
```yaml
Hard Baseline for Non-AI Nodes (anchored to current best practices):
  Core Processing Node: 1000 records ≤ 3s (P95), peak memory ≤ 200MB (Pillow baseline)
  GDI Precise Print Path: ≤ 8s
  xlwings Compatibility Path: ≤ 15s
  Any new implementation must not degrade below the current baseline.

AI Node Performance Standards:
  OCR Node: Batch size of 50 images, P95 latency ≤ 120s, peak memory ≤ 2GB
  LLM Node: Batch size of 10 texts, P95 latency ≤ 60s, peak memory ≤ 4GB
  AI Concurrency ≤ 1 (Hard Limit): When queuing/backpressure is triggered, GUI input echo < 200ms, main thread must not be blocked.
  Fallback Mechanism: Automatically fall back to rule-based solutions upon AI failure.
```

**Metrics and Gating** (New Section for NFR2)
```yaml
Performance Monitoring Requirements:
  - All nodes must report P95 latency, peak memory usage, and queue length to `/metrics` endpoint
  - Monitoring data exported in Prometheus format for integration with standard monitoring stacks
  - Real-time dashboards showing resource utilization and performance trends

CI/CD Performance Gates:
  - Pre-merge baseline validation required for all processing nodes
  - Pillow baseline: 1000 records ≤ 3s (P95), reject merge if exceeded
  - GDI precision path: 1000 records ≤ 8s (P95), reject merge if exceeded  
  - xlwings compatibility path: 1000 records ≤ 15s (P95), reject merge if exceeded
  - Memory leak detection: 4-hour long-run test with <5% memory growth
  - Automated performance regression detection with baseline comparison

Acceptance Gate Requirements:
  - All new nodes must pass performance gates before code merge
  - Performance test suite automatically triggered on PR creation
  - Manual override requires technical lead approval with documented justification
  - Post-deployment monitoring ensures production performance matches CI benchmarks
```

**NFR3**: **Memory Redline and Safety Margin** (Redline Revision)
```yaml
Resource Budget for 8GB RAM Environment (Peak Usage x 1.3 Safety Factor):
  Base System: 1331 MB    # Windows + Python environment (peak x 1.3)
  GUI Main Process: 666 MB # Tkinter interface (peak x 1.3)
  Excel COM: 333 MB        # Office integration (peak x 1.3)
  Node Engine: 65 MB       # Self-developed lightweight DAG engine (peak x 1.3)
  SQLite Queue: 83 MB      # Message queue storage (peak x 1.3)
  AI Model Pool: 3584 MB   # LLM peak adjusted for budget (reduced from 4096MB)
  OCR Processing: 260 MB   # UMI-OCR or PaddleOCR (peak x 1.3)
  Buffer Space: 334 MB     # Temp files and cache (adjusted)
  Total: 6656MB ≤ 6.5GB Target Redline

Resource Redline Control:
  - Target usage ≤ 6.5GB (6656MB, reserving ≥ 20% headroom).
  - Warning threshold: 6.3GB (6451MB) - triggers proactive monitoring and minor optimizations.
  - Over-threshold strategy: Backpressure → Queuing → Protection Mode (pause AI nodes, retain only rule-based paths).
  - Protection mode triggers when exceeding 6.3GB warning threshold.
  - Monitoring resumes within 10 minutes; AI concurrency ≤ 1 (Hard Limit).
```

**NFR4**: **Responsive Architecture** - Employ an asynchronous processing model to ensure GUI responsiveness, supporting long-running background tasks and real-time progress feedback.

**NFR5**: **Modular Design** - Loosely couple the core platform and business nodes to support independent development, testing, and deployment of nodes.

**NFR6**: **Industry Compliance** - The system must comply with national standards such as "General Functional Requirements for Electronic Records Management Systems" (GB/T39784-2021).

**NFR7**: **Extensibility** - The node architecture must support the registration and extension of new node types and the integration of third-party node plugins.

### Compatibility Requirements

**CR1**: **API Compatibility** - Core business interfaces (enhanced_height_calculator, generator) must remain backward compatible, requiring no modification to existing recipe systems.

**CR2**: **Data Compatibility** - The `app_config.json` format must be backward compatible, allowing existing user configurations to be seamlessly migrated to the new platform.

**CR3**: **UI Consistency** - The refactored user interface must maintain existing operational habits and visual layout, requiring no user retraining.

**CR4**: **Integration Compatibility** - Integration with Windows GDI API, Excel COM operations, and the file system must remain fully compatible.

**CR5**: **Data Security** - Implement end-to-end behavioral auditing, ensuring all operations are traceable to meet archive security management requirements.

