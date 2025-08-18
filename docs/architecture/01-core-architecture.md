# ADG Intelligent Archive Directory Platform - Comprehensive Architecture Document

## Document Information

**Document Type**: Brownfield Enhancement Architecture Document
**Version**: v1.0
**Creation Date**: 2025-08-17
**Last Updated**: 2025-08-17
**Maintainer**: Winston (Architect)

### Change Log

| Date | Version | Description | Author |
|------|------|------|------|
| 2025-08-17 | 1.0 | Comprehensive architecture design based on brownfield architecture and PRD | Winston |
| 2025-08-17 | 1.1 | Added security architecture design based on validation report | Winston |
| 2025-08-17 | 1.2 | Added dependency version management, development specifications, API design specifications | Winston |
| 2025-08-17 | 1.3 | Refined project management, documentation maintenance, summary, and outlook sections | Winston |

## Project Overview

### Project Introduction

ADG (Archive Directory Generator) Intelligent Archive Directory Platform is a major refactoring and upgrade of the existing archive directory generator. The project evolves from a dedicated Excel directory generation tool into an intelligent auxiliary platform that supports the complete archive digitalization process. It adopts a node-based workflow architecture and integrates AI/OCR capabilities, achieving a platform-oriented transformation while maintaining compatibility with existing functionalities.

### Evolution Goals

**Current State**: A single-purpose tool specializing in "directory conversion and printing".
**Target State**: An intelligent auxiliary platform covering 11 stages of the archive digitalization process.

**Archive Digitalization Process Coverage**:
- Existing: Directory Conversion, Printing
- New: Directory Entry, Directory Data Verification, Directory Data Re-verification, Archive Scanning, Image Conversion, etc.

### Core Value Proposition

1.  **Compatibility Guarantee**: Full compatibility with existing Excel generation and row height calculation functions.
2.  **Progressive Upgrade**: Smooth migration achieved through feature flags.
3.  **Intelligent Enhancement**: AI/OCR capabilities empower the entire archive processing workflow.
4.  **Hardware Optimization**: Optimal performance under the constraints of an i5 9400 + 8GB RAM.
5.  **Platform-based Architecture**: Node-based design supports flexible workflow configuration.

## Technology Stack Architecture

### Existing Technology Stack (Maintaining Compatibility)

| Category | Technology | Version | Status | Usage |
|------|------|------|------|------|
| Runtime | Python | 3.x | ✅ Maintained | Primary development language |
| GUI Framework | Tkinter | Built-in | ✅ Maintained | Desktop interface, log display |
| Excel Operations | xlwings | 0.28.x-0.31.x | ✅ Maintained | Excel automation, depends on Office |
| | openpyxl | 3.0.x-3.1.x | ✅ Maintained | Excel read/write, standalone library |
| | pywin32 | 305+ | ✅ Maintained | Windows COM automation |
| Image Processing | Pillow | 9.0.x-10.x | ✅ Maintained | Font measurement and image processing |
| Data Processing | pandas | 1.5.x-2.3.x | ✅ Maintained | Data analysis and processing |
| System Integration | win32print/win32gui | pywin32 | ✅ Maintained | Precise measurement via Windows GDI API |

### New Technology Stack (Intelligent Capabilities)

| Category | Technology Choice | Memory Budget | Usage | Rationale |
|------|----------|----------|------|----------|
| Workflow Engine | In-house SQLite DAG Engine | 65MB | Node scheduling and execution | Lightweight, controllable, no external dependencies |
| LLM Core | Hunyuan 1.8B/4B (INT4) | 3GB | Resident intelligent processing | Hard limit: Peak ≤ 4GB |
| LLM Extension | Qwen3-4B/7B (INT4) | 4GB | On-demand high-precision processing | Auto-unload when idle |
| OCR Main Channel | UMI-OCR (HTTP) | 200MB | Standard document recognition | Based on PaddleOCR, API-based |
| OCR Fallback | Embedded PaddleOCR+OpenVINO | 260MB | Offline processing | No network dependency |
| OCR Advanced | dots.ocr | On-demand | Complex layout processing | Formulas, tables, multilingual |
| Message Queue | SQLite WAL Mode | 83MB | Inter-node communication | Short transactions < 50ms |
| PDF Processing | PyMuPDF (fitz) | 100MB | Document processing | Supports dual-layer PDF |

### Hardware Resource Budget

**Precise Resource Allocation in an 8GB RAM Environment** (Peak × 1.3 safety factor):

```yaml
Memory Budget Allocation:
  Base System: 1331MB          # Windows + Python environment
  GUI Main Process: 666MB     # Tkinter interface
  Excel COM: 333MB             # Office integration
  Node Engine: 65MB            # In-house lightweight DAG engine
  SQLite Queue: 83MB           # Message queue storage
  AI Model Pool: 3584MB        # LLM peak ≤ 3.5GB (revised hard limit)
  OCR Processing: 260MB        # UMI-OCR or PaddleOCR
  Buffer Space: 534MB          # Temporary files and cache (reduced)
  Total: 6656MB = 6.5GB target red line

Resource Red Line Management:
  - Target usage ≤ 6.5GB (6656MB) (reserving ≥18.2% headroom)
  - Warning threshold: 6.3GB (6451MB) - trigger preemptive measures
  - Over-threshold strategy: 6.3GB Warning → 6.5GB Backpressure → Protection Mode
  - AI node concurrency ≤ 1 (hard limit)
```

## System Architecture Design

### Overall Architecture Diagram

```
ADG Intelligent Archive Directory Platform Architecture

┌─────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  Tkinter Main UI (Legacy Compatible) │  Workflow Visual Editor (New)     │
│  - Traditional directory config      │  - DAG node drag & drop editing   │
│  - Real-time log display             │  - Workflow template management   │
│  - Progress monitoring               │  - Parameter configuration UI     │
└─────────────────────────────────────────────────────────────────┘
                                   │
┌─────────────────────────────────────────────────────────────────┐
│                      Application Service Layer                    │
├─────────────────────────────────────────────────────────────────┤
│              │              │                │                  │
│  Legacy Gen   │  Workflow     │   Intelligent    │   Integration   │
│  Service      │  Service (New)│   Service (New)  │   Service (New) │
│  (Compatible) │              │                │                  │
│ ┌───────────┐ │ ┌──────────┐ │ ┌────────────┐ │ ┌──────────────┐ │
│ │generator  │ │ │WorkFlow  │ │ │LLMService  │ │ │APIGateway    │ │
│ │.py        │ │ │Engine    │ │ │OCRService  │ │ │FileWatcher   │ │
│ │recipes.py │ │ │NodeMgr   │ │ │QualityChk  │ │ │ExternalAPI   │ │
│ │height_calc│ │ │DAGParser │ │ │MetaExtract │ │ │NotifyService │ │
│ └───────────┘ │ └──────────┘ │ └────────────┘ │ └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                   │
┌─────────────────────────────────────────────────────────────────┐
│                      Node Execution Layer                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Data I/O Nodes         Processing Nodes   Intelligent Nodes   Control Nodes │
│ ┌─────────────────┐ ┌─────────────────┐ ┌──────────┐ ┌─────────┐ │
│ │FileInputNode    │ │DataTransform    │ │LLMNode   │ │Schedule │ │
│ │FileOutputNode   │ │FormatConvert    │ │OCRNode   │ │Condition│ │
│ │DatabaseInput    │ │RuleValidation   │ │QualityAI │ │FileWatch│ │
│ │APIInputNode     │ │FileOperation    │ │MetaAI    │ │Manual   │ │
│ └─────────────────┘ └─────────────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                   │
┌─────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  State Management      Resource Management  External Integration  System Integration │
│ ┌─────────────────┐ ┌─────────────────┐ ┌──────────┐ ┌─────────┐ │
│ │SQLite WAL       │ │MemoryManager    │ │UMI-OCR   │ │Windows  │ │
│ │ConfigManager    │ │ResourceMonitor  │ │Qwen-LLM  │ │GDI API  │ │
│ │AuditLogger      │ │GCScheduler      │ │External  │ │Excel COM│ │
│ │VersionControl   │ │BackPressure     │ │APIs      │ │PrintAPI │ │
│ └─────────────────┘ └─────────────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Core Module Analysis

#### 1. Legacy Generation Service (Maintaining Compatibility)

**Core Components**:
- `core/generator.py`: Core logic for Excel directory generation.
- `core/enhanced_height_calculator.py`: Triple-method row height calculation.
- `utils/recipes.py`: Directory generation recipe system.
- `core/transform_excel.py`: Excel format transformation.

**Triple Row Height Calculation Architecture**:
1.  **xlwings Method**: Native Excel AutoFit, depends on Office.
2.  **GDI Method**: Precise measurement via Windows GDI API, zero error match with printing.
3.  **Pillow Method**: Standalone calculation, no Office dependency, fastest speed.

**Performance Baseline Guarantee**:
- Pillow Method: 1000 records ≤ 3 seconds (P95), peak memory ≤ 200MB.
- GDI Method: ≤ 8 seconds.
- xlwings Method: ≤ 15 seconds.

#### 2. Workflow Engine (New Core)

**In-house SQLite DAG Engine**:
```python
class OptimizedNodeEngine:
    """Lightweight DAG engine based on SQLite WAL"""
  
    def __init__(self):
        # SQLite WAL mode configuration
        self.state_db = SQLiteStateManager(
            journal_mode="WAL",
            synchronous="NORMAL", 
            busy_timeout=5000,
            cache_size=10000
        )
      
        # Memory-aware scheduler
        self.scheduler = MemoryAwareScheduler(
            memory_limit_mb=6656,  # 6.5GB red line (consistent with budget)
            memory_warning_mb=6451, # 6.3GB warning threshold
            ai_concurrency=1,      # AI concurrency hard limit
            regular_concurrency=3
        )
```

**Key Features**:
- Memory footprint ≤ 50MB, 10x lighter than Airflow.
- Task latency of 10-50ms, supporting real-time response.
- WAL mode avoids read/write blocking, short transactions < 50ms.
- Exponential backoff retry mechanism, dead-letter queue for fault tolerance.

#### 3. Intelligent Processing Service (New)

**Two-Tier LLM Strategy**:
```python
class LLMStrategy:
    """Two-tier LLM strategy: resident lightweight + on-demand heavyweight"""
  
    def __init__(self):
        # Resident lightweight model
        self.resident_llm = HunyuanModel(
            model="hunyuan-1.8B-INT4",
            max_memory_mb=3072
        )
      
        # On-demand heavyweight model
        self.on_demand_llm = QwenModel(
            model="Qwen3-7B-Chat-INT4", 
            max_memory_mb=4096,
            auto_unload=True
        )
```

**Dual-Channel OCR Design**:
```python
class OCRDualChannel:
    """OCR dual-channel: standard channel + advanced channel"""
  
    def __init__(self):
        # Standard channel - batch-first
        self.standard_channel = UMIOCRNode(
            api_url="http://127.0.0.1:1224/api/ocr",
            fallback=PaddleOCRNode()
        )
      
        # Advanced channel - complex layouts
        self.advanced_channel = DotsOCRNode(
            trigger_conditions=[
                "complex_table", "mathematical_formula", 
                "multi_language", "handwritten_text"
            ]
        )
```

#### 4. Compatibility Architecture Design

**Backward API Compatibility Guarantee**:
```python
class CompatibilityLayer:
    """Ensures full backward compatibility for existing APIs"""
  
    def __init__(self):
        # Maintain existing interfaces
        self.legacy_generator = LegacyGenerator()
        self.new_engine = NodeEngine()
      
    def get_height_calculator(self, method="pillow"):
        """Maintain existing interface signature"""
        return self.legacy_generator.get_height_calculator(method)
      
    def generate_directory(self, config):
        """Existing generation logic remains unchanged"""
        if self.use_legacy_mode():
            return self.legacy_generator.generate(config)
        else:
            return self.new_engine.execute_workflow(config)
```

### Node Architecture System

#### Node Classification System

**1. Data I/O Nodes**:
- `FileInputNode`: File reading, supports Excel/CSV/JSON.
- `FileOutputNode`: File output, format conversion.
- `DatabaseInputNode`: Database queries.
- `APIInputNode`: Data fetching from REST APIs.

**2. Intelligent Processing Nodes**:
- `UMIOCRNode`: Document recognition based on UMI-OCR.
- `LLMProcessingNode`: Text processing based on Qwen.
- `MetadataExtractionNode`: Intelligent metadata extraction.
- `QualityCheckNode`: AI-assisted quality checking.

**3. Traditional Processing Nodes**:
- `RuleBasedValidationNode`: Rule validation based on Cerberus.
- `FileOperationNode`: File operations (copy, move, compress).
- `DataTransformationNode`: Data transformation and cleaning.
- `FormatConversionNode`: Format conversion (reuses existing logic).

**4. Control Nodes**:
- `FileWatcherNode`: Triggers on file system events.
- `ScheduleNode`: Scheduled task execution.
- `ConditionNode`: Conditional branching control.
- `ManualReviewNode`: Manual review checkpoint.

#### Node Interface Specification

```python
class ProcessingNode(ABC):
    """Base class for nodes, defining a unified interface"""
  
    @abstractmethod
    def process(self, input_data: Dict) -> Dict:
        """Core processing logic"""
        pass
      
    @abstractmethod
    def validate_input(self, input_data: Dict) -> bool:
        """Input validation"""
        pass
      
    @abstractmethod
    def get_schema(self) -> Dict:
        """Get the node's configuration schema"""
        pass
      
    def get_memory_usage(self) -> int:
        """Get memory usage"""
        return psutil.Process().memory_info().rss
      
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        return {
            "avg_latency": self.avg_latency,
            "success_rate": self.success_rate,
            "memory_peak": self.memory_peak
        }
```

### UI Architecture and Accessibility Design

#### Overview

Based on comprehensive accessibility requirements analysis, the ADG platform must establish modern UI architecture with full accessibility support. This includes comprehensive keyboard navigation, screen reader compatibility, and specialized accessibility features for archive management scenarios.

#### UI Accessibility Design Standards

##### Keyboard Navigation Framework

```python
class AccessibilityManager:
    """UI accessibility manager for the ADG platform"""
    
    def __init__(self):
        self.tab_order_registry = TabOrderRegistry()
        self.screen_reader_announcer = ScreenReaderAnnouncer()
        self.keyboard_handler = KeyboardNavigationHandler()
        
    def setup_accessibility_framework(self):
        """Initialize accessibility framework"""
        # Configure keyboard navigation
        self.setup_keyboard_navigation()
        
        # Configure screen reader support
        self.setup_screen_reader_support()
        
        # Configure high contrast themes
        self.setup_accessibility_themes()
        
    def setup_keyboard_navigation(self):
        """Configure comprehensive keyboard navigation"""
        # Tab order for main interface
        self.tab_order_registry.register_tab_sequence([
            'recipe_selector',
            'height_method_selector', 
            'file_path_input',
            'template_path_input',
            'output_path_input',
            'archive_range_input',
            'generate_button',
            'progress_display'
        ])
        
        # Keyboard shortcuts for main functions
        self.keyboard_handler.register_shortcuts({
            'Alt+t': 'focus_recipe_type',
            'Alt+h': 'focus_height_method',
            'Alt+f': 'focus_file_input',
            'Alt+g': 'start_generation',
            'Ctrl+o': 'open_file_dialog',
            'F1': 'show_help',
            'Escape': 'cancel_operation'
        })
```

##### Screen Reader and Assistive Technology Support

```python
class ScreenReaderSupport:
    """Screen reader compatibility layer"""
    
    def __init__(self):
        self.aria_labels = AriaLabelManager()
        self.live_regions = LiveRegionManager()
        self.status_announcer = StatusAnnouncer()
        
    def setup_aria_labels(self):
        """Configure ARIA labels for all interactive elements"""
        aria_config = {
            'recipe_combo': {
                'label': '档案目录类型选择',
                'description': '选择要生成的档案目录类型，包括全宗目录、案卷目录等'
            },
            'height_method_combo': {
                'label': '行高计算方案',
                'description': '选择行高计算方法：Pillow快速方案、GDI精确方案或xlwings方案'
            },
            'file_input_entry': {
                'label': '数据源文件路径',
                'description': '选择包含档案信息的Excel数据文件'
            },
            'generate_button': {
                'label': '开始生成目录',
                'description': '点击开始生成档案目录，预计处理时间根据数据量而定'
            }
        }
        
        for widget_id, config in aria_config.items():
            self.aria_labels.set_label(widget_id, config)
    
    def announce_status_change(self, status: str, detail: str = None):
        """Announce status changes to screen readers"""
        announcement = f"状态更新：{status}"
        if detail:
            announcement += f"。详情：{detail}"
        
        self.status_announcer.announce(announcement, priority='polite')
    
    def announce_progress(self, current: int, total: int, operation: str):
        """Announce progress updates"""
        progress_percent = int((current / total) * 100)
        announcement = f"{operation}进度：{progress_percent}%，已完成{current}项，共{total}项"
        
        self.status_announcer.announce(announcement, priority='assertive')
```

##### Color Contrast and Visual Accessibility Standards

```python
class AccessibilityThemeManager:
    """Accessibility theme management"""
    
    def __init__(self):
        self.themes = self.initialize_accessibility_themes()
        self.current_theme = 'default'
        self.contrast_checker = ContrastChecker()
        
    def initialize_accessibility_themes(self):
        """Initialize WCAG 2.1 AA compliant themes"""
        return {
            'high_contrast': {
                'bg': '#FFFFFF',           # Pure white background
                'fg': '#000000',           # Pure black text (21:1 contrast)
                'accent': '#0066CC',       # Blue accent (7.2:1 contrast)
                'error': '#CC0000',        # Red error (5.4:1 contrast)
                'success': '#006600',      # Green success (5.8:1 contrast)
                'warning': '#B37400',      # Orange warning (4.6:1 contrast)
                'focus': '#0052A3',        # Focus indicator (8.6:1 contrast)
                'disabled': '#767676'      # Disabled state (4.5:1 contrast)
            },
            'dark_mode': {
                'bg': '#1E1E1E',           # Dark background
                'fg': '#FFFFFF',           # White text (19.1:1 contrast)
                'accent': '#66B3FF',       # Light blue accent (8.2:1 contrast)
                'error': '#FF6B6B',        # Light red error (7.1:1 contrast)
                'success': '#51CF66',      # Light green success (9.2:1 contrast)
                'warning': '#FFD43B',      # Yellow warning (12.6:1 contrast)
                'focus': '#74C0FC',        # Light blue focus (9.8:1 contrast)
                'disabled': '#868E96'      # Disabled state (4.7:1 contrast)
            },
            'default': {
                'bg': '#F8F9FA',           # Light gray background
                'fg': '#212529',           # Dark gray text (16.1:1 contrast)
                'accent': '#0056B3',       # Blue accent (8.1:1 contrast)
                'error': '#DC3545',        # Red error (5.1:1 contrast)
                'success': '#28A745',      # Green success (6.4:1 contrast)
                'warning': '#FFC107',      # Yellow warning (1.6:1 on white, needs icon)
                'focus': '#007BFF',        # Focus indicator (6.1:1 contrast)
                'disabled': '#6C757D'      # Disabled state (4.6:1 contrast)
            }
        }
    
    def apply_theme(self, theme_name: str):
        """Apply accessibility theme to all widgets"""
        if theme_name not in self.themes:
            raise ValueError(f"Unknown theme: {theme_name}")
        
        theme = self.themes[theme_name]
        self.current_theme = theme_name
        
        # Apply theme to all registered widgets
        for widget in self.get_all_widgets():
            self.apply_theme_to_widget(widget, theme)
    
    def validate_contrast_ratios(self, theme: dict) -> dict:
        """Validate WCAG 2.1 AA contrast ratios"""
        validation_results = {}
        
        # Normal text: 4.5:1 minimum
        # Large text (18pt+ or 14pt bold): 3:1 minimum  
        # Non-text elements: 3:1 minimum
        
        tests = [
            ('text_on_background', theme['fg'], theme['bg'], 4.5),
            ('accent_on_background', theme['accent'], theme['bg'], 4.5),
            ('error_on_background', theme['error'], theme['bg'], 4.5),
            ('success_on_background', theme['success'], theme['bg'], 4.5),
            ('focus_indicator', theme['focus'], theme['bg'], 3.0),
            ('disabled_text', theme['disabled'], theme['bg'], 4.5)
        ]
        
        for test_name, fg_color, bg_color, min_ratio in tests:
            ratio = self.contrast_checker.calculate_ratio(fg_color, bg_color)
            validation_results[test_name] = {
                'ratio': ratio,
                'passes': ratio >= min_ratio,
                'minimum': min_ratio
            }
        
        return validation_results
```

##### Archive Management Specific Accessibility Features

```python
class ArchiveAccessibilityFeatures:
    """Archive management specific accessibility features"""
    
    def __init__(self):
        self.data_announcer = DataAnnouncer()
        self.validation_feedback = ValidationFeedback()
        self.progress_narrator = ProgressNarrator()
    
    def setup_archive_specific_features(self):
        """Configure archive-specific accessibility features"""
        # Archive number range validation with audio feedback
        self.setup_archive_range_validation()
        
        # File processing progress with detailed narration
        self.setup_detailed_progress_feedback()
        
        # Data integrity announcements
        self.setup_data_integrity_feedback()
    
    def setup_archive_range_validation(self):
        """Real-time validation with accessibility feedback"""
        validation_messages = {
            'invalid_format': '档号格式无效，请使用正确的档号格式，例如：A001-A100',
            'range_too_large': '档号范围过大，建议单次处理不超过1000条记录以确保性能',
            'missing_files': '部分档号对应的文件未找到，请检查文件路径设置',
            'validation_success': '档号范围验证通过，共识别到{count}条有效记录'
        }
        
        for event, message in validation_messages.items():
            self.validation_feedback.register_message(event, message)
    
    def announce_processing_milestone(self, milestone: str, context: dict):
        """Announce key processing milestones"""
        announcements = {
            'files_loaded': f"文件加载完成，共{context['file_count']}个文件，{context['record_count']}条记录",
            'height_calculation_start': f"开始行高计算，使用{context['method']}方案",
            'pagination_complete': f"分页计算完成，共生成{context['page_count']}页",
            'excel_generation_complete': f"Excel文件生成完成，文件大小{context['file_size']}MB",
            'process_complete': f"目录生成完成，耗时{context['duration']}秒，请检查输出文件"
        }
        
        if milestone in announcements:
            self.data_announcer.announce(
                announcements[milestone],
                priority='assertive',
                category='milestone'
            )
```

#### Modern Tkinter Component Architecture

##### Component-Based Design System

```python
class ComponentArchitecture:
    """Modern component-based architecture for Tkinter"""
    
    def __init__(self):
        self.component_registry = ComponentRegistry()
        self.state_manager = GlobalStateManager()
        self.event_bus = ComponentEventBus()
        
    def initialize_component_system(self):
        """Initialize the component-based architecture"""
        # Register core components
        self.register_core_components()
        
        # Setup state management
        self.setup_centralized_state()
        
        # Configure component communication
        self.setup_event_bus()

class AccessibleComponent(ABC):
    """Base class for accessible UI components"""
    
    def __init__(self, parent, component_id: str, **kwargs):
        self.parent = parent
        self.component_id = component_id
        self.state_manager = kwargs.get('state_manager')
        self.accessibility_manager = kwargs.get('accessibility_manager')
        
        # Accessibility properties
        self.aria_label = kwargs.get('aria_label', '')
        self.aria_description = kwargs.get('aria_description', '')
        self.keyboard_shortcuts = kwargs.get('keyboard_shortcuts', {})
        
        self.create_component()
        self.setup_accessibility()
        self.setup_state_bindings()
    
    @abstractmethod
    def create_component(self):
        """Create the visual component"""
        pass
    
    def setup_accessibility(self):
        """Setup accessibility features"""
        # Setup ARIA properties
        if self.aria_label:
            self.set_aria_label(self.aria_label)
        
        if self.aria_description:
            self.set_aria_description(self.aria_description)
        
        # Setup keyboard navigation
        self.setup_keyboard_navigation()
        
        # Setup focus management
        self.setup_focus_management()
    
    def setup_keyboard_navigation(self):
        """Setup keyboard navigation for the component"""
        for shortcut, action in self.keyboard_shortcuts.items():
            self.bind_keyboard_shortcut(shortcut, action)
    
    def setup_focus_management(self):
        """Setup focus indicators and management"""
        if hasattr(self, 'widget'):
            self.widget.bind('<FocusIn>', self.on_focus_in)
            self.widget.bind('<FocusOut>', self.on_focus_out)
    
    def on_focus_in(self, event):
        """Handle focus in event"""
        # Add visual focus indicator
        self.add_focus_indicator()
        
        # Announce to screen reader
        if self.accessibility_manager:
            self.accessibility_manager.announce_focus_change(
                self.component_id, 
                self.aria_label
            )
    
    def on_focus_out(self, event):
        """Handle focus out event"""
        # Remove visual focus indicator
        self.remove_focus_indicator()

class RecipeSelector(AccessibleComponent):
    """Accessible recipe selector component"""
    
    def create_component(self):
        """Create the recipe selector widget"""
        self.frame = ttk.Frame(self.parent)
        
        # Label with proper association
        self.label = ttk.Label(
            self.frame, 
            text="目录类型：",
            font=('SimSun', 11)
        )
        
        # Combobox with accessibility features
        self.combobox = ttk.Combobox(
            self.frame,
            values=['全宗目录', '案卷目录', '卷内目录', '简化目录'],
            state='readonly',
            width=20,
            font=('SimSun', 11)
        )
        
        # Associate label with combobox for screen readers
        self.combobox.configure(
            takefocus=True
        )
        
        # Layout
        self.label.pack(side=tk.LEFT, padx=(0, 5))
        self.combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.widget = self.combobox  # For accessibility framework
    
    def setup_state_bindings(self):
        """Setup state management bindings"""
        if self.state_manager:
            # Listen for recipe changes
            self.state_manager.subscribe(
                'current_recipe', 
                self.on_recipe_changed
            )
            
            # Bind combobox changes to state
            self.combobox.bind('<<ComboboxSelected>>', self.on_selection_changed)
    
    def on_selection_changed(self, event):
        """Handle selection change"""
        selected_value = self.combobox.get()
        recipe_mapping = {
            '全宗目录': 'collection_directory',
            '案卷目录': 'file_unit_directory', 
            '卷内目录': 'in_file_directory',
            '简化目录': 'simplified_directory'
        }
        
        recipe_key = recipe_mapping.get(selected_value)
        if recipe_key and self.state_manager:
            self.state_manager.set_state('current_recipe', recipe_key)
        
        # Announce selection to screen reader
        if self.accessibility_manager:
            self.accessibility_manager.announce_selection_change(
                f"已选择目录类型：{selected_value}"
            )
    
    def on_recipe_changed(self, new_recipe: str, old_recipe: str):
        """Handle recipe change from state manager"""
        value_mapping = {
            'collection_directory': '全宗目录',
            'file_unit_directory': '案卷目录',
            'in_file_directory': '卷内目录', 
            'simplified_directory': '简化目录'
        }
        
        display_value = value_mapping.get(new_recipe)
        if display_value:
            self.combobox.set(display_value)

class PathSelector(AccessibleComponent):
    """Accessible file path selector component"""
    
    def __init__(self, parent, path_type: str = "file", **kwargs):
        self.path_type = path_type
        self.file_types = kwargs.get('file_types', [('Excel files', '*.xlsx'), ('All files', '*.*')])
        super().__init__(parent, **kwargs)
    
    def create_component(self):
        """Create the path selector widget"""
        self.frame = ttk.Frame(self.parent)
        
        # Label
        self.label = ttk.Label(
            self.frame,
            text=self.get_label_text(),
            font=('SimSun', 11)
        )
        
        # Entry with validation
        self.entry = ttk.Entry(
            self.frame,
            width=50,
            font=('SimSun', 11)
        )
        
        # Browse button
        self.browse_button = ttk.Button(
            self.frame,
            text="浏览...",
            command=self.browse_path,
            width=8
        )
        
        # Layout
        self.label.pack(anchor=tk.W, pady=(0, 2))
        
        entry_frame = ttk.Frame(self.frame)
        entry_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.browse_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        entry_frame.pack_configure(in_=self.frame)
        
        self.widget = self.entry  # For accessibility framework
        
        # Setup real-time validation
        self.entry.bind('<KeyRelease>', self.on_path_changed)
        self.entry.bind('<FocusOut>', self.validate_path)
    
    def get_label_text(self) -> str:
        """Get appropriate label text for path type"""
        labels = {
            'file': '数据源文件：',
            'template': '模板文件：',
            'output': '输出文件夹：'
        }
        return labels.get(self.path_type, '文件路径：')
    
    def browse_path(self):
        """Open file/folder browser dialog"""
        if self.path_type == 'output':
            # Folder selection
            path = filedialog.askdirectory(
                title=f"选择{self.get_label_text()}",
                initialdir=os.path.expanduser('~/Documents')
            )
        else:
            # File selection
            path = filedialog.askopenfilename(
                title=f"选择{self.get_label_text()}",
                filetypes=self.file_types,
                initialdir=os.path.expanduser('~/Documents')
            )
        
        if path:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, path)
            self.validate_path()
            
            # Announce to screen reader
            if self.accessibility_manager:
                filename = os.path.basename(path)
                self.accessibility_manager.announce_selection_change(
                    f"已选择文件：{filename}"
                )
    
    def on_path_changed(self, event):
        """Handle real-time path changes"""
        path = self.entry.get().strip()
        
        # Real-time feedback
        if path and os.path.exists(path):
            self.entry.configure(style='Valid.TEntry')
        elif path:
            self.entry.configure(style='Invalid.TEntry')
        else:
            self.entry.configure(style='TEntry')
    
    def validate_path(self, event=None):
        """Validate the entered path"""
        path = self.entry.get().strip()
        
        if not path:
            return True  # Empty is allowed
        
        if self.path_type == 'output':
            is_valid = os.path.isdir(path) or os.path.isdir(os.path.dirname(path))
        else:
            is_valid = os.path.isfile(path)
        
        if not is_valid and self.accessibility_manager:
            error_msg = f"路径无效：{path}" if path else "请选择有效的文件路径"
            self.accessibility_manager.announce_validation_error(
                self.component_id,
                error_msg
            )
        
        return is_valid

class ProgressDisplay(AccessibleComponent):
    """Accessible progress display component"""
    
    def create_component(self):
        """Create the progress display widget"""
        self.frame = ttk.Frame(self.parent)
        
        # Progress label
        self.progress_label = ttk.Label(
            self.frame,
            text="进度：",
            font=('SimSun', 11)
        )
        
        # Progress bar with accessibility features
        self.progress_bar = ttk.Progressbar(
            self.frame,
            mode='determinate',
            length=300
        )
        
        # Progress text (for screen readers)
        self.progress_text = ttk.Label(
            self.frame,
            text="等待开始...",
            font=('SimSun', 9),
            foreground='#666666'
        )
        
        # Status text area
        self.status_frame = ttk.Frame(self.frame)
        self.status_text = tk.Text(
            self.status_frame,
            height=6,
            width=60,
            font=('SimSun', 9),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        
        # Scrollbar for status text
        self.scrollbar = ttk.Scrollbar(
            self.status_frame,
            orient=tk.VERTICAL,
            command=self.status_text.yview
        )
        self.status_text.configure(yscrollcommand=self.scrollbar.set)
        
        # Layout
        self.progress_label.pack(anchor=tk.W, pady=(5, 2))
        self.progress_bar.pack(fill=tk.X, pady=(0, 2))
        self.progress_text.pack(anchor=tk.W, pady=(0, 5))
        
        self.status_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.widget = self.progress_bar  # For accessibility framework
    
    def update_progress(self, current: int, total: int, status: str = ""):
        """Update progress with accessibility announcements"""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        
        # Update visual progress
        self.progress_bar.configure(value=progress_percent)
        self.progress_text.configure(text=f"{current}/{total} ({progress_percent}%)")
        
        # Add status message
        if status:
            self.add_status_message(status)
        
        # Announce to screen reader (with throttling)
        if self.accessibility_manager and current % 10 == 0:  # Every 10 items
            self.accessibility_manager.announce_progress(
                current, total, progress_percent, status
            )
    
    def add_status_message(self, message: str):
        """Add a status message to the display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.status_text.configure(state=tk.NORMAL)
        self.status_text.insert(tk.END, formatted_message)
        self.status_text.see(tk.END)
        self.status_text.configure(state=tk.DISABLED)
```

##### State Management and Component Communication

```python
class GlobalStateManager:
    """Centralized state management for components"""
    
    def __init__(self):
        self.state = {
            'current_recipe': 'collection_directory',
            'height_method': 'pillow',
            'file_paths': {
                'data_source': '',
                'template': '',
                'output': ''
            },
            'archive_range': {
                'start': '',
                'end': ''
            },
            'processing_status': 'idle',
            'progress': {
                'current': 0,
                'total': 0,
                'status': ''
            },
            'validation_errors': [],
            'selected_files': set()
        }
        
        self.observers = defaultdict(list)
        self.state_history = []
        
    def subscribe(self, key: str, callback: callable):
        """Subscribe to state changes"""
        self.observers[key].append(callback)
    
    def unsubscribe(self, key: str, callback: callable):
        """Unsubscribe from state changes"""
        if callback in self.observers[key]:
            self.observers[key].remove(callback)
    
    def set_state(self, key: str, value: any):
        """Update state and notify observers"""
        old_value = self.get_state(key)
        
        # Update state using dot notation for nested keys
        self._set_nested_state(self.state, key, value)
        
        # Record state change
        self.state_history.append({
            'timestamp': datetime.now(),
            'key': key,
            'old_value': old_value,
            'new_value': value
        })
        
        # Notify observers
        if key in self.observers and old_value != value:
            for callback in self.observers[key]:
                try:
                    callback(value, old_value)
                except Exception as e:
                    logger.error(f"Error in state observer: {e}")
    
    def get_state(self, key: str, default: any = None):
        """Get state value using dot notation"""
        return self._get_nested_state(self.state, key, default)
    
    def _set_nested_state(self, state_dict: dict, key: str, value: any):
        """Set nested state value"""
        keys = key.split('.')
        current = state_dict
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def _get_nested_state(self, state_dict: dict, key: str, default: any):
        """Get nested state value"""
        keys = key.split('.')
        current = state_dict
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

class ComponentEventBus:
    """Event bus for component communication"""
    
    def __init__(self):
        self.event_handlers = defaultdict(list)
        self.event_history = []
    
    def subscribe(self, event_type: str, handler: callable, priority: int = 0):
        """Subscribe to events with priority"""
        self.event_handlers[event_type].append((priority, handler))
        # Sort by priority (higher first)
        self.event_handlers[event_type].sort(key=lambda x: x[0], reverse=True)
    
    def emit(self, event_type: str, data: any = None, source: str = None):
        """Emit an event to all subscribers"""
        event = {
            'type': event_type,
            'data': data,
            'source': source,
            'timestamp': datetime.now()
        }
        
        self.event_history.append(event)
        
        # Call all handlers
        for priority, handler in self.event_handlers[event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    def emit_async(self, event_type: str, data: any = None, source: str = None):
        """Emit event asynchronously"""
        threading.Thread(
            target=self.emit,
            args=(event_type, data, source),
            daemon=True
        ).start()
```

##### Responsive Layout and Adaptive Design

```python
class ResponsiveLayoutManager:
    """Responsive layout management for different screen sizes"""
    
    def __init__(self, root_window):
        self.root = root_window
        self.breakpoints = {
            'small': 800,    # Small screens
            'medium': 1200,  # Medium screens
            'large': 1600    # Large screens
        }
        self.current_layout = 'medium'
        self.layout_adapters = {}
        
        # Monitor window size changes
        self.root.bind('<Configure>', self.on_window_resize)
        
    def register_layout_adapter(self, component_id: str, adapter: 'LayoutAdapter'):
        """Register a layout adapter for a component"""
        self.layout_adapters[component_id] = adapter
    
    def on_window_resize(self, event):
        """Handle window resize events"""
        if event.widget == self.root:
            width = event.width
            new_layout = self.determine_layout(width)
            
            if new_layout != self.current_layout:
                self.apply_layout(new_layout)
                self.current_layout = new_layout
    
    def determine_layout(self, width: int) -> str:
        """Determine layout based on window width"""
        if width < self.breakpoints['small']:
            return 'small'
        elif width < self.breakpoints['medium']:
            return 'medium'
        else:
            return 'large'
    
    def apply_layout(self, layout_type: str):
        """Apply layout to all registered adapters"""
        for component_id, adapter in self.layout_adapters.items():
            try:
                adapter.apply_layout(layout_type)
            except Exception as e:
                logger.error(f"Error applying layout to {component_id}: {e}")

class LayoutAdapter:
    """Base class for component layout adaptation"""
    
    def __init__(self, component):
        self.component = component
        
    def apply_layout(self, layout_type: str):
        """Apply layout based on screen size"""
        if layout_type == 'small':
            self.apply_compact_layout()
        elif layout_type == 'medium':
            self.apply_standard_layout()
        else:
            self.apply_expanded_layout()
    
    def apply_compact_layout(self):
        """Apply compact layout for small screens"""
        # Stack components vertically
        # Hide non-essential elements
        # Reduce padding and margins
        pass
    
    def apply_standard_layout(self):
        """Apply standard layout for medium screens"""
        # Default balanced layout
        pass
    
    def apply_expanded_layout(self):
        """Apply expanded layout for large screens"""
        # Show additional information
        # Use more horizontal space
        # Add helpful sidebars or panels
        pass
```

#### Performance Optimization for Large Data Sets

```python
class VirtualizedListView:
    """Virtualized list view for handling large datasets"""
    
    def __init__(self, parent, data_source, item_height=25):
        self.parent = parent
        self.data_source = data_source
        self.item_height = item_height
        self.visible_range = (0, 50)  # Only render visible items
        
        self.create_virtualized_view()
        
    def create_virtualized_view(self):
        """Create virtualized scrollable view"""
        self.canvas = tk.Canvas(self.parent, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=self.on_scroll)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Frame for visible items
        self.visible_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(0, 0, anchor="nw", window=self.visible_frame)
        
        # Layout
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind events
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.canvas.bind('<MouseWheel>', self.on_mousewheel)
        
        # Initial render
        self.update_visible_items()
        
    def update_visible_items(self):
        """Update only the visible items"""
        # Clear existing items
        for widget in self.visible_frame.winfo_children():
            widget.destroy()
        
        # Render visible items
        start_idx, end_idx = self.visible_range
        data_items = self.data_source.get_items(start_idx, end_idx)
        
        for i, item in enumerate(data_items):
            item_widget = self.create_item_widget(self.visible_frame, item, start_idx + i)
            item_widget.pack(fill="x", pady=1)
        
        # Update scroll region
        total_height = len(self.data_source) * self.item_height
        self.canvas.configure(scrollregion=(0, 0, 0, total_height))
    
    def on_scroll(self, *args):
        """Handle scroll events"""
        # Calculate new visible range
        canvas_height = self.canvas.winfo_height()
        scroll_top = float(args[1]) * len(self.data_source) * self.item_height
        
        start_idx = max(0, int(scroll_top / self.item_height) - 5)  # Buffer
        end_idx = min(len(self.data_source), start_idx + int(canvas_height / self.item_height) + 10)
        
        if (start_idx, end_idx) != self.visible_range:
            self.visible_range = (start_idx, end_idx)
            self.update_visible_items()
        
        self.canvas.yview(*args)
    
    def create_item_widget(self, parent, item_data, index):
        """Create widget for individual item"""
        frame = ttk.Frame(parent)
        
        # Item content based on data
        label = ttk.Label(
            frame,
            text=f"[{index:04d}] {item_data.get('title', '未知文件')}",
            font=('SimSun', 9)
        )
        label.pack(side="left", fill="x", expand=True)
        
        # Status indicator
        status = item_data.get('status', 'unknown')
        status_colors = {
            'processed': '#28a745',
            'error': '#dc3545',
            'pending': '#ffc107',
            'unknown': '#6c757d'
        }
        
        status_indicator = tk.Label(
            frame,
            text="●",
            fg=status_colors.get(status, '#6c757d'),
            font=('SimSun', 12)
        )
        status_indicator.pack(side="right")
        
        return frame
```

这种现代化的组件架构确保了ADG平台在保持原有功能的同时，提供了完整的可访问性支持和现代化的用户体验。通过组件化设计，系统具有良好的可维护性和可扩展性，能够适应未来的功能扩展需求。

### Data Model and Flow

#### Core Data Models

```python
@dataclass
class ArchiveDocument:
    """Data model for an archive document"""
    id: str
    title: str
    category: str
    metadata: Dict[str, Any]
    content: Optional[str] = None
    ocr_result: Optional[Dict] = None
    quality_score: Optional[float] = None
    validation_result: Optional[Dict] = None
  
@dataclass
class WorkflowExecution:
    """Workflow execution state"""
    workflow_id: str
    execution_id: str
    status: str  # pending, running, completed, failed
    current_node: str
    progress: float
    start_time: datetime
    error_info: Optional[Dict] = None
  
@dataclass
class NodeResult:
    """Node execution result"""
    node_id: str
    status: str
    output_data: Dict[str, Any]
    execution_time: float
    memory_usage: int
    error_info: Optional[str] = None
```

#### Data Flow Patterns

**Legacy Mode** (Maintaining Compatibility):
```
Excel Input → Data Parsing → Row Height Calculation → Pagination Algorithm → Excel Output
```

**Node-based Mode** (New):
```
Input Node → Intelligent Processing Node Chain → Quality Check → Format Conversion → Output Node
    ↓
SQLite Queue → State Management → Audit Log → Version Control
```

