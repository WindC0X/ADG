import logging
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import sys
import os
import pandas as pd

# 添加当前目录到Python路径（支持直接运行）
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from utils.recipes import (
    create_aj_index,
    create_jn_or_jh_index,
    create_qy_full_index,
)
from core.enhanced_height_calculator import (
    get_height_calculator,
    set_calculation_method,
    get_available_methods
)
from utils.config_manager import get_config_manager
from utils.file_validator import validate_excel_file, validate_output_directory
from utils.feature_manager import get_feature_manager, is_feature_enabled


class QueueHandler(logging.Handler):
    """
    一个自定义的日志处理器，将日志记录发送到一个队列中，
    以便在GUI线程中安全地更新Text控件。
    支持精简模式，过滤详细的调试信息。
    """

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        # 定义需要在GUI中精简显示的关键词
        self.simplify_keywords = [
            'twip比较', '页码分割', 'pt值:', '当前行高', '缩放',
            '正在计算行高', '测量文本', '字体规格', '末页', '填充', 'twip'
        ]
        # 定义完全过滤的关键词（不在GUI显示）
        self.filter_keywords = [
            'DEBUG', 'trace', '调试',
            '开始更新文件列表', '开始解析档案数据', '解析得到', '过滤后剩余', '文件列表更新完成',
            '成功读取Excel文件', '使用列', '添加文件', '解析完成，预计生成', '开始生成文件列表',
            '分组数量', '目录类型:', '路径不存在或为空', '路径:', '列名:', '行数:'
        ]

    def emit(self, record):
        formatted_msg = self.format(record)
        
        # 检查是否需要完全过滤
        if any(keyword in formatted_msg for keyword in self.filter_keywords):
            return
            
        # 检查是否需要精简显示
        if any(keyword in formatted_msg for keyword in self.simplify_keywords):
            simplified_msg = self._simplify_message(formatted_msg)
            if simplified_msg:
                self.log_queue.put(simplified_msg)
        else:
            self.log_queue.put(formatted_msg)
    
    def _simplify_message(self, message):
        """将详细的技术日志转换为用户友好的简要信息"""
        try:
            # 提取时间戳
            timestamp = message.split(' - ')[0] if ' - ' in message else ''
            
            # 页码分割信息 -> 简化为分页信息
            if '页码分割' in message and 'twip比较' in message:
                # 提取关键信息：行数和文件名
                import re
                line_match = re.search(r'页码分割于(\d+)行后', message)
                file_match = re.search(r'\((.*?)\)', message)
                
                if line_match and file_match:
                    line_num = line_match.group(1)
                    filename = file_match.group(1)
                    return f"{timestamp} - 📄 {filename}: 第{line_num}行处分页"
            
            # 行高计算 -> 简化为处理进度
            elif '正在计算行高' in message:
                if '(' in message and ')' in message:
                    filename = message.split('(')[1].split(')')[0]
                    return f"{timestamp} - 🔄 正在处理: {filename}"
            
            # 末页填充信息 -> 简化显示
            elif '末页' in message and '填充' in message:
                # 提取关键信息：文件名、页码、填充行数
                import re
                file_match = re.search(r'案卷\s+([^,]+)', message)
                page_match = re.search(r'页\s+(\d+)', message) 
                fill_match = re.search(r'填充\s+(\d+)空行', message)
                
                if file_match and page_match and fill_match:
                    filename = file_match.group(1)
                    page_num = page_match.group(1)
                    fill_rows = fill_match.group(1)
                    return f"{timestamp} - 📋 {filename}: 第{page_num}页填充{fill_rows}行"
            
            # 文件处理完成
            elif '处理完成' in message or '生成完成' in message:
                return message  # 保持完整
                
            # 错误和警告保持完整
            elif any(level in message for level in ['ERROR', 'WARNING', '错误', '警告']):
                return message
                
            # 其他情况返回None，表示不显示
            return None
            
        except Exception:
            # 出错时返回原消息
            return message


class DirectoryGeneratorGUI(tk.Tk):
    """
    Tkinter图形用户界面主应用类。
    """

    def __init__(self):
        super().__init__()
        
        # 初始化配置管理器
        self.config_manager = get_config_manager()
        
        # 初始化特性标志管理器
        self.feature_manager = get_feature_manager()
        self._initialize_feature_flags()
        
        # 初始化线程管理
        self.current_task_thread = None
        self.shutdown_flag = threading.Event()
        
        # 初始化打印服务
        from utils.print_service import get_print_service
        self.print_service = get_print_service()
        
        # 初始化文件列表相关属性
        self.file_list_data = []  # 存储文件列表数据
        self.filtered_file_list = []  # 存储过滤后的文件列表
        self.selected_files = set()  # 存储用户选择的文件
        
        self.title("统一目录生成器 v4.0 (Tkinter版)")
        
        # 设置窗口最小尺寸和默认尺寸（更小的窗口）
        self.minsize(650, 350)  # 设置更小的最小尺寸
        
        # 从配置加载窗口几何，如果配置不合理则使用默认值
        geometry = self.config_manager.get_window_geometry()
        if not geometry or "x" not in geometry:
            geometry = "700x400"  # 更小的默认窗口尺寸
        self.geometry(geometry)

        # 设置日志自动保存
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        from datetime import datetime
        log_filename = os.path.join(log_dir, f"adg_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        
        # 文件处理器（完整日志）
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
            datefmt="%H:%M:%S",
            handlers=[self.queue_handler, file_handler],
        )

        self.create_widgets()
        self.load_config()  # 加载配置
        self.refresh_printers()  # 初始化打印机列表
        self.after(100, self.process_log_queue)
        
        # 初始化完成后显示当前方案信息
        self.after(200, self.show_initial_method_info)
        
        # 延迟初始化文件列表
        self.after(300, self.update_file_list)
        
        # 启动打印状态监控
        self.after(1000, self.monitor_print_status)
        
        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """创建并布局所有的UI控件。"""
        main_frame = ttk.Frame(self, padding="1")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 顶部紧凑配置区域 ---
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, expand=False, pady=(0, 0))
        
        # 第一行：目录类型、行高方案、档号范围
        config_row1 = ttk.Frame(top_frame)
        config_row1.pack(fill=tk.X, pady=(0, 0))
        
        # 目录类型
        ttk.Label(config_row1, text="目录类型:").pack(side=tk.LEFT)
        self.recipe_var = tk.StringVar()
        self.recipe_combo = ttk.Combobox(
            config_row1,
            textvariable=self.recipe_var,
            values=["卷内目录", "案卷目录", "全引目录", "简化目录"],
            state="readonly",
            width=8
        )
        self.recipe_combo.pack(side=tk.LEFT, padx=(1, 5))
        self.recipe_combo.current(0)

        # 行高方案
        ttk.Label(config_row1, text="行高方案:").pack(side=tk.LEFT)
        height_container = ttk.Frame(config_row1)
        height_container.pack(side=tk.LEFT, padx=(1, 5))
        
        # 获取可用方案
        available_methods = get_available_methods()
        method_display_names = {
            'xlwings': 'xlwings',
            'gdi': 'GDI',
            'pillow': 'Pillow'
        }
        
        method_values = [method_display_names.get(method, method) for method in available_methods]
        
        self.height_method_var = tk.StringVar()
        self.height_method_combo = ttk.Combobox(
            height_container,
            textvariable=self.height_method_var,
            values=method_values,
            state="readonly",
            width=8
        )
        self.height_method_combo.pack(side=tk.LEFT)
        self.height_method_combo.current(0)
        
        # 档号范围（同行）
        ttk.Label(config_row1, text="起始档号:").pack(side=tk.LEFT)
        self.options = {}
        self.options["start_file"] = ttk.Entry(config_row1, width=8)
        self.options["start_file"].pack(side=tk.LEFT, padx=(1, 5))
        self.options["start_file"].bind('<FocusOut>', lambda e: self.on_option_changed("start_file", e.widget.get()))

        ttk.Label(config_row1, text="结束档号:").pack(side=tk.LEFT)
        self.options["end_file"] = ttk.Entry(config_row1, width=8)
        self.options["end_file"].pack(side=tk.LEFT, padx=(1, 0))
        self.options["end_file"].bind('<FocusOut>', lambda e: self.on_option_changed("end_file", e.widget.get()))
        
        # 绑定选择变化事件
        self.height_method_combo.bind('<<ComboboxSelected>>', self.on_height_method_changed)
        self.recipe_combo.bind('<<ComboboxSelected>>', self.on_recipe_changed)
        
        # 存储方案映射
        self.available_methods = available_methods
        self.method_display_names = method_display_names

        # --- 路径配置（紧凑型） ---
        self.path_frame = ttk.LabelFrame(main_frame, text="配置路径", padding="1")
        self.path_frame.pack(fill=tk.X, expand=False, pady=(0, 1))

        self.paths = {}
        self.path_widgets = {}  # 存储所有路径相关的控件
        
        # 创建路径网格容器
        self.path_grid = ttk.Frame(self.path_frame)
        self.path_grid.pack(fill=tk.X, expand=True)
        self.path_grid.columnconfigure(1, weight=3)

        # 定义所有可能的路径配置
        self.all_path_specs = {
            "jn_catalog_path": "卷内目录:",
            "aj_catalog_path": "案卷目录:",
            "jh_catalog_path": "简化目录:",
            "template_path": "模板:",
            "output_folder": "输出:",
        }

        # 定义每种目录类型需要的路径
        self.recipe_path_mapping = {
            "卷内目录": ["jn_catalog_path", "template_path", "output_folder"],
            "案卷目录": ["aj_catalog_path", "template_path", "output_folder"],
            "全引目录": ["jn_catalog_path", "aj_catalog_path", "template_path", "output_folder"],
            "简化目录": ["jh_catalog_path", "template_path", "output_folder"],
        }

        # 创建所有路径控件（初始时隐藏）
        self.create_all_path_widgets()
        
        # 添加配置管理按钮
        config_buttons_frame = ttk.Frame(self.path_frame)
        config_buttons_frame.pack(fill=tk.X, pady=(1, 0))
        
        ttk.Button(
            config_buttons_frame,
            text="清空路径",
            command=self.clear_current_paths
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            config_buttons_frame,
            text="重置配置",
            command=self.reset_config
        ).pack(side=tk.LEFT)

        # --- 控制与日志区域 ---
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 2))

        # 左侧：紧凑控制区域（固定宽度，不扩展）
        left_control = ttk.Frame(control_frame)
        left_control.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=(0, 3))
        
        # 中间：文件列表区域（减小占用空间）
        file_list_frame = ttk.LabelFrame(control_frame, text="文件列表", padding="3")
        file_list_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=(0, 3))

        # 操作控制（紧凑布局）
        control_row = ttk.Frame(file_list_frame)
        control_row.pack(fill=tk.X, pady=(0, 2))
        
        # 选择控制
        ttk.Button(control_row, text="全选", command=self.select_all_files, width=6).pack(side=tk.LEFT, padx=1)
        ttk.Button(control_row, text="全不选", command=self.deselect_all_files, width=6).pack(side=tk.LEFT, padx=1)
        ttk.Button(control_row, text="反选", command=self.invert_selection, width=6).pack(side=tk.LEFT, padx=1)
        ttk.Button(control_row, text="刷新", command=self.update_file_list, width=6).pack(side=tk.LEFT, padx=1)
        
        # 转换模式选择
        ttk.Separator(control_row, orient='vertical').pack(side=tk.LEFT, fill='y', padx=5)
        self.convert_mode_var = tk.StringVar(value="all")
        ttk.Radiobutton(control_row, text="全部转换", variable=self.convert_mode_var, value="all").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(control_row, text="选中转换", variable=self.convert_mode_var, value="selected").pack(side=tk.LEFT, padx=2)
        
        # 排序状态提示已移除

        # 文件列表显示（使用TreeView提供表格格式）
        # 创建TreeView（减少高度节省空间）
        columns = ('序号', '文件名', '目录条数')
        self.file_treeview = ttk.Treeview(file_list_frame, columns=columns, show='headings', height=8, selectmode='extended')
        
        # 初始化排序状态
        self.sort_column = '序号'  # 当前排序列
        self.sort_reverse = False  # 是否倒序
        
        # 设置列标题并绑定点击事件
        for col in columns:
            self.file_treeview.heading(col, text=col, command=lambda c=col: self.on_column_click(c))
        
        # 设置列宽（优化空间利用，总宽度控制在350左右）
        self.file_treeview.column('序号', width=40, anchor='center')
        self.file_treeview.column('文件名', width=240, anchor='w')
        self.file_treeview.column('目录条数', width=60, anchor='center')
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(file_list_frame, orient='vertical', command=self.file_treeview.yview)
        self.file_treeview.configure(yscrollcommand=scrollbar.set)
        
        # 布局（不扩展，固定宽度）
        self.file_treeview.pack(side='left', fill='y', expand=False, pady=2)
        scrollbar.pack(side='right', fill='y')
        
        # 绑定选择事件
        self.file_treeview.bind('<<TreeviewSelect>>', self.on_file_selection_changed)

        # 打印设置区域（紧凑布局）
        print_frame = ttk.LabelFrame(left_control, text="打印设置", padding="3")
        print_frame.pack(fill=tk.X, expand=False, pady=(0, 2))
        
        # 第一行：模式选择
        mode_frame = ttk.Frame(print_frame)
        mode_frame.pack(fill=tk.X, pady=1)
        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT)
        
        self.print_mode_var = tk.StringVar(value="none")
        self.print_mode_var.trace('w', self.on_print_mode_changed)
        ttk.Radiobutton(mode_frame, text="不打印", variable=self.print_mode_var, value="none").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_frame, text="直接", variable=self.print_mode_var, value="direct").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_frame, text="批量", variable=self.print_mode_var, value="batch").pack(side=tk.LEFT, padx=2)
        
        # 第二行：打印机、份数、批量按钮
        printer_frame = ttk.Frame(print_frame)
        printer_frame.pack(fill=tk.X, pady=1)
        ttk.Label(printer_frame, text="打印机:").pack(side=tk.LEFT)
        
        self.printer_var = tk.StringVar()
        self.printer_combo = ttk.Combobox(printer_frame, textvariable=self.printer_var, width=12, state="readonly")
        self.printer_combo.pack(side=tk.LEFT, padx=2)
        
        self.refresh_printer_btn = ttk.Button(printer_frame, text="刷新", command=self.refresh_printers, width=5)
        self.refresh_printer_btn.pack(side=tk.LEFT, padx=2)
        
        # 第三行：份数和批量打印
        copies_batch_frame = ttk.Frame(print_frame)
        copies_batch_frame.pack(fill=tk.X, pady=1)
        
        ttk.Label(copies_batch_frame, text="份数:").pack(side=tk.LEFT)
        
        self.print_copies_var = tk.StringVar(value="1")
        copies_spinbox = ttk.Spinbox(copies_batch_frame, from_=1, to=10, width=3, textvariable=self.print_copies_var)
        copies_spinbox.pack(side=tk.LEFT, padx=2)
        
        self.batch_print_btn = ttk.Button(copies_batch_frame, text="批量打印", command=self.batch_print_files, state="disabled", width=10)
        self.batch_print_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 第四行：打印状态
        self.print_status_var = tk.StringVar(value="队列:0|完成:0|失败:0")
        self.print_status_label = ttk.Label(print_frame, textvariable=self.print_status_var, font=("Arial", 7))
        self.print_status_label.pack(fill=tk.X, pady=1)
        
        # 间隔控制（单行紧凑布局）
        interval_frame = ttk.Frame(print_frame)
        interval_frame.pack(fill=tk.X, pady=1)
        
        self.interval_enabled_var = tk.BooleanVar(value=True)
        interval_checkbox = ttk.Checkbutton(
            interval_frame, 
            text="间隔", 
            variable=self.interval_enabled_var,
            command=self.on_interval_settings_changed
        )
        interval_checkbox.pack(side=tk.LEFT)
        
        ttk.Label(interval_frame, text="每").pack(side=tk.LEFT, padx=(5, 0))
        
        self.interval_task_count_var = tk.StringVar(value="3")
        task_count_spinbox = ttk.Spinbox(
            interval_frame, 
            from_=1, 
            to=20, 
            width=2, 
            textvariable=self.interval_task_count_var,
            command=self.on_interval_settings_changed
        )
        task_count_spinbox.pack(side=tk.LEFT, padx=1)
        task_count_spinbox.bind('<KeyRelease>', lambda e: self.on_interval_settings_changed())
        
        ttk.Label(interval_frame, text="个休息").pack(side=tk.LEFT)
        
        self.interval_seconds_var = tk.StringVar(value="50")
        seconds_spinbox = ttk.Spinbox(
            interval_frame, 
            from_=10, 
            to=300, 
            width=2, 
            textvariable=self.interval_seconds_var,
            command=self.on_interval_settings_changed
        )
        seconds_spinbox.pack(side=tk.LEFT, padx=1)
        seconds_spinbox.bind('<KeyRelease>', lambda e: self.on_interval_settings_changed())
        
        ttk.Label(interval_frame, text="秒").pack(side=tk.LEFT)
        
        self.skip_rest_btn = ttk.Button(
            interval_frame, 
            text="跳过", 
            command=self.skip_printer_rest,
            state="disabled",
            width=4
        )
        self.skip_rest_btn.pack(side=tk.RIGHT)
        
        # 间隔状态显示
        self.interval_status_var = tk.StringVar() 
        self.interval_status_label = ttk.Label(left_control, textvariable=self.interval_status_var, font=("Arial", 7), foreground="blue")
        self.interval_status_label.pack(fill=tk.X, pady=1)

        # 进度和控制区域
        progress_control_frame = ttk.Frame(left_control)
        progress_control_frame.pack(fill=tk.X, pady=2)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_control_frame, 
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, pady=1)
        
        # 进度标签
        self.progress_label = ttk.Label(progress_control_frame, text="准备就绪", font=("Arial", 8))
        self.progress_label.pack(pady=1)
        
        # 开始按钮
        button_container = ttk.Frame(left_control)
        button_container.pack(pady=2)
        
        self.start_button = ttk.Button(
            button_container, text="开始生成", command=self.run_generation_thread, width=15
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 预创建取消按钮但不显示
        self.cancel_button = ttk.Button(
            button_container, 
            text="取消任务", 
            command=self.cancel_generation,
            width=10
        )
        # 初始时不显示取消按钮

        # 右侧：日志输出（适应小窗口）
        log_frame = ttk.LabelFrame(control_frame, text="日志", padding="3")
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3, 0))
        self.log_text = ScrolledText(log_frame, state="disabled", height=12, width=50, wrap=tk.WORD, font=("Consolas", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def show_initial_method_info(self):
        """显示初始方案信息"""
        try:
            calculator = get_height_calculator()
            current_method = calculator.method
            available_methods = get_available_methods()
            
            logging.info("=" * 50)
            logging.info("统一目录生成器已启动")
            logging.info(f"当前行高计算方案: {current_method}")
            logging.info(f"可用方案: {', '.join(available_methods)}")
            logging.info("可在界面中切换不同的行高计算方案")
            logging.info("=" * 50)
            
        except Exception as e:
            logging.error(f"显示方案信息失败: {e}")

    def on_height_method_changed(self, event):
        """当行高计算方案选择改变时的回调函数"""
        selected_display = self.height_method_var.get()
        
        # 找到对应的实际方案名
        selected_method = None
        for method in self.available_methods:
            if self.method_display_names.get(method, method) == selected_display:
                selected_method = method
                break
        
        if selected_method:
            try:
                # 切换到选定的方案
                set_calculation_method(selected_method)
                
                # 保存到配置
                self.config_manager.set_last_height_method(selected_method)
                self.config_manager.save_config()
                
                # 在日志中显示切换信息
                logging.info(f"行高计算方案已切换到: {selected_method}")
                
                # 显示方案详细信息
                method_descriptions = {
                    'xlwings': '使用Excel原生AutoFit功能，速度快但可能在打印预览时溢出',
                    'gdi': '使用Windows GDI API精确测量，完美匹配打印预览（0.0pt误差）',
                    'pillow': '使用Pillow独立计算，高精度且无需打印机依赖'
                }
                
                description = method_descriptions.get(selected_method, selected_method)
                logging.info(f"方案说明: {description}")
                
            except Exception as e:
                logging.error(f"切换行高计算方案失败: {e}")
                messagebox.showerror("错误", f"切换行高计算方案失败: {e}")

    def on_recipe_changed(self, event):
        """当目录类型选择改变时的回调函数"""
        selected_recipe = self.recipe_var.get()
        self.config_manager.set_last_recipe(selected_recipe)
        self.config_manager.save_config()
        logging.info(f"目录类型已切换到: {selected_recipe}")
        
        # 更新路径显示
        self.update_path_visibility()
        
        # 更新文件列表
        self.update_file_list()

    def create_all_path_widgets(self):
        """创建所有路径控件"""
        for i, (key, text) in enumerate(self.all_path_specs.items()):
            # 创建标签
            label = ttk.Label(self.path_grid, text=text)
            
            # 创建输入框
            entry = ttk.Entry(self.path_grid, width=40)
            entry.bind('<FocusOut>', lambda e, k=key: self.on_path_changed(k, e.widget.get()))
            
            # 创建浏览按钮
            is_dir = "folder" in key
            button = ttk.Button(
                self.path_grid,
                text="浏览",
                command=lambda e=entry, d=is_dir, k=key: self.browse_path(e, d, k),
                width=6
            )
            
            # 存储控件引用
            self.path_widgets[key] = {
                'label': label,
                'entry': entry, 
                'button': button,
                'row': i
            }
            self.paths[key] = entry
            
            # 初始状态下不显示
            # 控件会在update_path_visibility中显示

    def update_path_visibility(self):
        """根据选择的目录类型更新路径控件的可见性"""
        selected_recipe = self.recipe_var.get()
        required_paths = self.recipe_path_mapping.get(selected_recipe, [])
        
        # 隐藏所有控件
        for key, widgets in self.path_widgets.items():
            widgets['label'].grid_remove()
            widgets['entry'].grid_remove()
            widgets['button'].grid_remove()
        
        # 显示需要的控件
        current_row = 0
        for path_key in required_paths:
            if path_key in self.path_widgets:
                widgets = self.path_widgets[path_key]
                widgets['label'].grid(row=current_row, column=0, sticky=tk.W, padx=3, pady=1)
                widgets['entry'].grid(row=current_row, column=1, sticky=tk.EW, padx=3, pady=1)
                widgets['button'].grid(row=current_row, column=2, sticky=tk.E, padx=3, pady=1)
                current_row += 1
        
        # 更新界面状态标题
        path_count = len(required_paths)
        self.path_frame.config(text=f"3. 配置路径 (需要 {path_count} 项)")

    def clear_current_paths(self):
        """清空当前显示的路径输入框"""
        selected_recipe = self.recipe_var.get()
        required_paths = self.recipe_path_mapping.get(selected_recipe, [])
        
        if required_paths and messagebox.askyesno("确认", f"确定要清空当前 [{selected_recipe}] 的所有路径吗？"):
            for path_key in required_paths:
                if path_key in self.paths:
                    self.paths[path_key].delete(0, tk.END)
                    self.config_manager.set_path(path_key, "")
            
            self.config_manager.save_config()
            logging.info(f"已清空 [{selected_recipe}] 的所有路径")

    def on_path_changed(self, path_key, path_value):
        """当路径改变时的回调函数"""
        self.config_manager.set_path(path_key, path_value)
        self.config_manager.save_config()
        
        # 如果是目录文件路径变更，更新文件列表
        if path_key in ["jn_catalog_path", "aj_catalog_path", "jh_catalog_path"]:
            self.update_file_list()

    def on_option_changed(self, option_key, option_value):
        """当可选参数改变时的回调函数"""
        self.config_manager.set_option(option_key, option_value)
        self.config_manager.save_config()
        
        # 如果是档号范围变更，更新文件列表
        if option_key in ["start_file", "end_file"]:
            self.update_file_list()

    def load_config(self):
        """从配置文件加载设置"""
        try:
            # 加载目录类型选择
            last_recipe = self.config_manager.get_last_recipe()
            recipe_values = ["卷内目录", "案卷目录", "全引目录", "简化目录"]
            if last_recipe in recipe_values:
                self.recipe_var.set(last_recipe)

            # 加载行高计算方案
            last_method = self.config_manager.get_last_height_method()
            if last_method in self.available_methods:
                display_name = self.method_display_names.get(last_method, last_method)
                self.height_method_var.set(display_name)
                set_calculation_method(last_method)

            # 加载路径配置
            paths_config = self.config_manager.get_paths()
            for path_key, entry_widget in self.paths.items():
                path_value = paths_config.get(path_key, "")
                if path_value:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, path_value)

            # 加载可选参数
            options_config = self.config_manager.get_options()
            for option_key, entry_widget in self.options.items():
                option_value = options_config.get(option_key, "")
                if option_value:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, option_value)
            
            # 加载打印间隔控制配置
            interval_config = self.config_manager.get_print_interval_config()
            self.interval_enabled_var.set(interval_config.get('enabled', True))
            self.interval_task_count_var.set(str(interval_config.get('task_count', 3)))
            self.interval_seconds_var.set(str(interval_config.get('interval_seconds', 50)))
            
            # 更新打印服务的间隔配置
            self.print_service.set_interval_config(interval_config)

            # 更新路径显示（重要：在加载配置后更新）
            self.update_path_visibility()

            logging.info("配置已加载")

        except Exception as e:
            logging.warning(f"加载配置失败: {e}")

    def on_closing(self):
        """窗口关闭时的处理"""
        try:
            # 设置关闭标志
            self.shutdown_flag.set()
            
            # 如果有任务正在运行，询问用户是否要等待
            if self.current_task_thread and self.current_task_thread.is_alive():
                if messagebox.askyesno("任务进行中", 
                                     "有任务正在运行，是否等待任务完成？\n"
                                     "选择'否'将强制关闭程序（可能导致数据丢失）"):
                    # 等待任务完成
                    logging.info("等待任务完成...")
                    self.current_task_thread.join(timeout=30)  # 最多等待30秒
                    
                    if self.current_task_thread.is_alive():
                        messagebox.showwarning("警告", "任务仍在运行，强制关闭程序")
            
            # 关闭打印服务和所有相关线程
            if hasattr(self, 'print_service'):
                logging.info("正在关闭打印服务...")
                self.print_service.shutdown(timeout=3.0)  # 3秒超时
                
                # 清理单例实例
                from utils.print_service import cleanup_print_service
                cleanup_print_service()
            
            # 保存窗口几何信息
            geometry = self.geometry()
            self.config_manager.set_window_geometry(geometry)
            self.config_manager.save_config()
            
            logging.info("程序正在安全关闭...")
            
        except Exception as e:
            logging.warning(f"关闭程序时发生异常: {e}")
        finally:
            self.destroy()

    def browse_path(self, entry_widget, is_directory, path_key):
        """打开文件/文件夹对话框并更新输入框。"""
        if is_directory:
            path = filedialog.askdirectory()
            if path:
                # 验证目录路径安全性
                if validate_output_directory(path):
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, path)
                    # 保存到配置
                    self.config_manager.set_path(path_key, path)
                    self.config_manager.save_config()
                    logging.info(f"已选择输出目录: {path}")
                else:
                    messagebox.showerror("路径错误", "选择的目录不存在或没有写入权限")
        else:
            path = filedialog.askopenfilename(
                filetypes=[
                    ("Excel 文件", "*.xlsx *.xls"),
                    ("所有文件", "*.*"),
                ]
            )
            if path:
                # 验证文件路径安全性
                if validate_excel_file(path):
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, path)
                    # 保存到配置
                    self.config_manager.set_path(path_key, path)
                    self.config_manager.save_config()
                    logging.info(f"已选择文件: {path}")
                    
                    # 如果是档案数据文件，自动更新文件列表
                    if path_key in ['jn_catalog_path', 'aj_catalog_path', 'jh_catalog_path']:
                        self.after(100, self.update_file_list)  # 延迟更新避免界面卡顿
                        
                else:
                    messagebox.showerror("文件错误", 
                                       "选择的文件不存在、格式不支持或文件过大\n"
                                       "请选择有效的Excel文件（.xlsx或.xls，小于100MB）")

    def reset_config(self):
        """重置所有配置到默认值"""
        if messagebox.askyesno("确认", "确定要重置所有配置到默认值吗？这将清空所有路径和选项。"):
            # 重置配置管理器
            self.config_manager.config = self.config_manager._get_default_config()
            self.config_manager.save_config()
            
            # 重新加载界面
            self.load_config()
            logging.info("配置已重置到默认值")

    def _initialize_feature_flags(self):
        """初始化特性标志配置。"""
        from utils.feature_manager import FeatureFlagStatus, ValidationMode
        
        # 创建节点引擎特性标志
        try:
            self.feature_manager.create_flag(
                name="node_engine",
                description="Enable node-based execution engine for directory generation",
                status=FeatureFlagStatus.DISABLED,  # 初始为禁用状态
                rollout_percentage=0.0,
                validation_mode=ValidationMode.STRICT,
                expires_in_days=90
            )
            logging.info("Created node_engine feature flag")
        except ValueError:
            # 标志已存在，跳过
            logging.debug("node_engine feature flag already exists")
        
        # 创建影子写入验证标志
        try:
            self.feature_manager.create_flag(
                name="shadow_validation",
                description="Enable shadow-write validation between legacy and node implementations",
                status=FeatureFlagStatus.DISABLED,
                validation_mode=ValidationMode.TOLERANT,
                expires_in_days=30
            )
            logging.info("Created shadow_validation feature flag")
        except ValueError:
            logging.debug("shadow_validation feature flag already exists")

    def process_log_queue(self):
        """从队列中获取日志消息并显示在文本控件中。"""
        try:
            batch_size = 20  # 增加批量处理数量，加快显示速度
            messages = []
            
            for _ in range(batch_size):
                try:
                    record = self.log_queue.get(block=False)
                    messages.append(record)
                except queue.Empty:
                    break
            
            if messages:
                self.log_text.configure(state="normal")
                self.log_text.insert(tk.END, "\n".join(messages) + "\n")
                # 限制日志行数，防止内存占用过多
                lines = self.log_text.get("1.0", tk.END).split("\n")
                if len(lines) > 500:  # 保留最后500行
                    self.log_text.delete("1.0", f"{len(lines)-500}.0")
                self.log_text.configure(state="disabled")
                self.log_text.see(tk.END)
                
        except Exception as e:
            # 防止日志处理异常影响主程序
            pass
        self.after(100, self.process_log_queue)  # 提高更新频率，从200ms改为100ms

    def update_progress(self, value, text):
        """更新进度条和标签"""
        self.after(0, lambda: self._safe_update_progress(value, text))
    
    def _safe_update_progress(self, value, text):
        """线程安全的进度更新"""
        try:
            self.progress_var.set(value)
            self.progress_label.config(text=text)
        except:
            pass
    
    def monitor_print_status(self):
        """监控打印状态"""
        try:
            if hasattr(self, 'print_service'):
                stats = self.print_service.get_print_stats()
                pending_count = self.print_service.get_pending_print_count()
                
                status_text = f"打印队列: {pending_count} | 已完成: {stats['total_completed']} | 失败: {stats['total_failed']}"
                self.print_status_var.set(status_text)
                
                # 监控当前选择的打印机的间隔状态
                current_printer = self.printer_var.get()
                if current_printer:
                    rest_info = self.print_service.get_printer_rest_info(current_printer)
                    
                    if rest_info['is_resting']:
                        # 显示休息状态和倒计时
                        remaining = rest_info['remaining_seconds']
                        interval_text = f"打印暂时停止，剩余 {remaining} 秒"
                        self.interval_status_var.set(interval_text)
                        self.skip_rest_btn.config(state="normal")
                    else:
                        # 显示当前任务计数
                        task_count = rest_info['task_count']
                        if task_count > 0:
                            interval_text = f"当前打印机已完成 {task_count} 个任务"
                            self.interval_status_var.set(interval_text)
                        else:
                            self.interval_status_var.set("")
                        self.skip_rest_btn.config(state="disabled")
                else:
                    self.interval_status_var.set("")
                    self.skip_rest_btn.config(state="disabled")
                    
        except Exception as e:
            logging.error(f"监控打印状态时发生异常: {e}")
            self.interval_status_var.set("状态监控异常")
            self.skip_rest_btn.config(state="disabled")
        
        # 每2秒更新一次状态
        self.after(2000, self.monitor_print_status)
    
    def on_print_mode_changed(self, *args):
        """当打印模式改变时的回调"""
        mode = self.print_mode_var.get()
        if mode == "batch":
            self.batch_print_btn.config(state="normal")
        else:
            self.batch_print_btn.config(state="disabled")
    
    def on_interval_settings_changed(self):
        """当间隔控制设置改变时的回调"""
        try:
            enabled = self.interval_enabled_var.get()
            task_count = int(self.interval_task_count_var.get())
            interval_seconds = int(self.interval_seconds_var.get())
            
            # 验证数值范围
            if task_count < 1 or task_count > 20:
                messagebox.showwarning("警告", "任务数量必须在1-20之间")
                self.interval_task_count_var.set("3")
                return
            
            if interval_seconds < 1 or interval_seconds > 300:
                messagebox.showwarning("警告", "休息时间必须在1-300秒之间")
                self.interval_seconds_var.set("10")  # 改为更合理的默认值
                return
            
            # 保存配置
            interval_config = {
                'enabled': enabled,
                'task_count': task_count,
                'interval_seconds': interval_seconds
            }
            
            self.config_manager.set_print_interval_config(interval_config)
            self.config_manager.save_config()
            
            # 更新打印服务配置
            self.print_service.set_interval_config(interval_config)
            
            logging.info(f"打印间隔控制配置已更新: {interval_config}")
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
        except Exception as e:
            logging.error(f"更新间隔控制配置失败: {e}")
    
    def skip_printer_rest(self):
        """跳过当前打印机的休息时间"""
        try:
            current_printer = self.printer_var.get()
            if not current_printer:
                messagebox.showwarning("警告", "请选择打印机")
                return
            
            success = self.print_service.skip_printer_rest(current_printer)
            if success:
                messagebox.showinfo("信息", f"已跳过打印机 {current_printer} 的休息时间")
                logging.info(f"用户手动跳过打印机 {current_printer} 的休息时间")
            else:
                messagebox.showinfo("信息", f"打印机 {current_printer} 当前没有在休息")
                
        except Exception as e:
            logging.error(f"跳过休息时间失败: {e}")
            messagebox.showerror("错误", f"跳过休息时间失败: {e}")
    
    def parse_archive_data(self, catalog_path):
        """解析档案数据文件，生成将要输出的目录文件列表"""
        try:
            # 处理.xls文件转换
            if catalog_path.endswith('.xls'):
                from core.transform_excel import xls2xlsx
                catalog_path = xls2xlsx(catalog_path)
            
            # 读取Excel数据
            df = pd.read_excel(catalog_path)
            logging.info(f"成功读取Excel文件，列名: {list(df.columns)}, 行数: {len(df)}")
            
            # 根据档案数据按档号分组，生成将要输出的文件列表
            file_list = []
            
            # 尝试多种可能的档号列名
            possible_file_number_columns = ['案卷档号', '档号', '文件号', '编号', 'file_number', 'number', '序号']
            file_number_col = None
            
            for col in possible_file_number_columns:
                if col in df.columns:
                    file_number_col = col
                    break
            
            if file_number_col:
                logging.info(f"使用列 '{file_number_col}' 作为档号列")
                
                # 按档号分组统计
                file_groups = {}
                for idx, row in df.iterrows():
                    try:
                        file_number = str(row[file_number_col]).strip()
                        if file_number and file_number != 'nan':
                            # 对于案卷档号，每个不同的档号就是一个分组
                            # 不需要去掉后缀，因为每个档号对应一个独立的档案
                            main_number = file_number
                            
                            if main_number not in file_groups:
                                file_groups[main_number] = 0
                            file_groups[main_number] += 1
                    except Exception as row_error:
                        logging.warning(f"跳过第{idx}行，解析错误: {row_error}")
                        continue
                
                # 生成文件列表
                logging.info(f"开始生成文件列表，分组数量: {len(file_groups)}")
                for main_number, item_count in file_groups.items():
                    # 生成预期的输出文件名（与实际生成逻辑保持一致）
                    # 从日志看：卷内目录_C001-ZYZS2023-Y-1105.xlsx
                    safe_name = main_number.replace('·', '')  # 移除·符号
                    display_name = f"卷内目录_{safe_name}"
                    
                    logging.info(f"添加文件: {display_name}, 条目数: {item_count}")
                    file_list.append({
                        'file_number': main_number,
                        'display_name': display_name,
                        'item_count': item_count
                    })
                
            else:
                # 如果没有找到档号列，假设生成单个文件
                logging.warning(f"未找到档号列，可用列: {list(df.columns)}，假设生成单个文件")
                file_list.append({
                    'file_number': "未知档号",
                    'display_name': "目录文件",
                    'item_count': len(df)
                })
            
            logging.info(f"解析完成，预计生成 {len(file_list)} 个目录文件")
            return file_list
        except Exception as e:
            logging.error(f"解析档案数据失败: {e}")
            return []
    
    def update_file_list(self):
        """更新文件列表显示"""
        try:
            logging.info("开始更新文件列表")
            # 获取当前选择的目录类型和对应路径
            recipe = self.recipe_var.get()
            catalog_path = None
            
            if recipe == "卷内目录":
                catalog_path = self.paths["jn_catalog_path"].get()
            elif recipe == "案卷目录":
                catalog_path = self.paths["aj_catalog_path"].get()
            elif recipe == "简化目录":
                catalog_path = self.paths["jh_catalog_path"].get()
            elif recipe == "全引目录":
                # 优先使用卷内目录数据
                catalog_path = self.paths["jn_catalog_path"].get()
                if not catalog_path:
                    catalog_path = self.paths["aj_catalog_path"].get()
            
            logging.info(f"目录类型: {recipe}, 路径: {catalog_path}")
            
            if not catalog_path or not os.path.exists(catalog_path):
                logging.warning(f"路径不存在或为空: {catalog_path}")
                self.file_list_data = []
                self.filtered_file_list = []
                self.refresh_file_listbox()
                return
            
            # 解析档案数据
            logging.info(f"开始解析档案数据: {catalog_path}")
            self.file_list_data = self.parse_archive_data(catalog_path)
            logging.info(f"解析得到 {len(self.file_list_data)} 条数据")
            
            # 应用档号范围过滤
            self.apply_file_range_filter()
            logging.info(f"过滤后剩余 {len(self.filtered_file_list)} 条数据")
            
            # 应用排序
            self.apply_file_sort()
            
            # 刷新界面显示
            self.refresh_file_listbox()
            logging.info("文件列表更新完成")
            
        except Exception as e:
            logging.error(f"更新文件列表失败: {e}")
            import traceback
            logging.error(f"详细错误: {traceback.format_exc()}")
    
    
    def apply_file_range_filter(self):
        """根据档号范围过滤文件列表"""
        start_file = self.options["start_file"].get().strip()
        end_file = self.options["end_file"].get().strip()
        
        if not start_file and not end_file:
            self.filtered_file_list = self.file_list_data.copy()
            return
        
        filtered = []
        for file_info in self.file_list_data:
            file_number = file_info['file_number']
            
            # 检查起始档号
            if start_file and file_number < start_file:
                continue
                
            # 检查结束档号
            if end_file and file_number > end_file:
                continue
                
            filtered.append(file_info)
        
        self.filtered_file_list = filtered
    

    def on_column_click(self, column):
        """列标题点击排序"""
        # 如果点击的是当前排序列，则切换升降序
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            # 切换到新列，默认升序
            self.sort_column = column
            self.sort_reverse = False
        
        # 更新列标题显示排序状态
        self.update_column_headers()
        
        # 执行排序
        self.apply_file_sort()
        self.refresh_file_listbox()
    
    def update_column_headers(self):
        """更新列标题显示排序状态"""
        columns = ['序号', '文件名', '目录条数']
        for col in columns:
            if col == self.sort_column:
                # 显示排序箭头
                arrow = ' ↓' if self.sort_reverse else ' ↑'
                self.file_treeview.heading(col, text=f"{col}{arrow}")
            else:
                # 清除其他列的箭头
                self.file_treeview.heading(col, text=col)

    def apply_file_sort(self):
        """应用文件排序"""
        if not self.filtered_file_list:
            return
        
        # 根据选择的列进行排序
        if self.sort_column == '序号':
            # 按序号排序（实际上就是原始顺序）
            pass  # filtered_file_list已经是按顺序的
        elif self.sort_column == '文件名':
            # 按文件名排序
            self.filtered_file_list.sort(
                key=lambda x: x['display_name'], 
                reverse=self.sort_reverse
            )
        elif self.sort_column == '目录条数':
            # 按目录条数排序
            self.filtered_file_list.sort(
                key=lambda x: x['item_count'], 
                reverse=self.sort_reverse
            )
        
        # 如果是序号列排序，需要特殊处理
        if self.sort_column == '序号' and self.sort_reverse:
            self.filtered_file_list.reverse()
    
    def refresh_file_listbox(self):
        """刷新文件列表显示"""
        # 清空现有数据
        for item in self.file_treeview.get_children():
            self.file_treeview.delete(item)
        
        # 添加数据到TreeView
        for idx, file_info in enumerate(self.filtered_file_list, 1):
            self.file_treeview.insert('', 'end', values=(
                idx,  # 序号
                file_info['display_name'],  # 文件名  
                file_info['item_count']  # 目录条数
            ))
        
        # 更新列标题显示
        self.update_column_headers()
        
        # 恢复用户选择状态
        self.restore_file_selection()
    
    def on_file_selection_changed(self, event):
        """文件选择改变时的回调"""
        selected_items = self.file_treeview.selection()
        # 获取选择项的索引
        self.selected_files = set()
        for item in selected_items:
            # 获取该项在TreeView中的索引
            children = self.file_treeview.get_children()
            if item in children:
                idx = children.index(item)
                self.selected_files.add(idx)

    def select_all_files(self):
        """全选文件"""
        # 选择所有项
        children = self.file_treeview.get_children()
        self.file_treeview.selection_set(children)
        self.selected_files = set(range(len(self.filtered_file_list)))

    def deselect_all_files(self):
        """取消全选"""
        self.file_treeview.selection_remove(self.file_treeview.selection())
        self.selected_files.clear()

    def invert_selection(self):
        """反选"""
        children = self.file_treeview.get_children()
        current_selection = set(self.file_treeview.selection())
        all_items = set(children)
        new_selection = all_items - current_selection
        
        # 清除当前选择
        self.file_treeview.selection_remove(self.file_treeview.selection())
        # 设置新选择
        self.file_treeview.selection_set(list(new_selection))
        
        # 更新索引集合
        self.selected_files = set()
        for item in new_selection:
            if item in children:
                idx = children.index(item)
                self.selected_files.add(idx)

    def restore_file_selection(self):
        """恢复文件选择状态"""
        children = self.file_treeview.get_children()
        items_to_select = []
        for index in self.selected_files:
            if index < len(children):
                items_to_select.append(children[index])
        
        if items_to_select:
            self.file_treeview.selection_set(items_to_select)
    
    def refresh_printers(self):
        """刷新打印机列表"""
        try:
            printers = self.print_service.refresh_printers()
            self.printer_combo['values'] = printers
            
            # 设置默认打印机
            default_printer = self.print_service.get_default_printer()
            if default_printer and default_printer in printers:
                self.printer_var.set(default_printer)
            elif printers:
                self.printer_var.set(printers[0])
            
            logging.info(f"已刷新打印机列表，发现 {len(printers)} 台打印机")
            
        except Exception as e:
            logging.error(f"刷新打印机列表失败: {e}")
            messagebox.showerror("错误", f"刷新打印机列表失败: {e}")
    
    def batch_print_files(self):
        """批量打印文件"""
        if not self.printer_var.get():
            messagebox.showwarning("警告", "请选择打印机")
            return
        
        # 选择要打印的Excel文件
        file_paths = filedialog.askopenfilenames(
            title="选择要打印的Excel文件",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        
        if not file_paths:
            return
        
        try:
            copies = int(self.print_copies_var.get())
            printer_name = self.printer_var.get()
            
            # 添加打印任务到队列
            for file_path in file_paths:
                self.print_service.add_print_job(file_path, printer_name, copies)
            
            # 启动批量打印
            self.print_service.start_batch_printing()
            
            logging.info(f"已添加 {len(file_paths)} 个文件到打印队列")
            messagebox.showinfo("信息", f"已添加 {len(file_paths)} 个文件到打印队列\n打印机: {printer_name}")
            
        except ValueError:
            messagebox.showerror("错误", "打印份数必须是有效的数字")
        except Exception as e:
            logging.error(f"批量打印失败: {e}")
            messagebox.showerror("错误", f"批量打印失败: {e}")

    def run_generation_thread(self):
        """在单独的线程中启动目录生成任务，以防UI冻结。"""
        # 检查是否有任务正在运行
        if self.current_task_thread and self.current_task_thread.is_alive():
            messagebox.showwarning("任务进行中", "已有任务正在运行，请等待完成后再启动新任务")
            return
        
        # 创建取消标志
        self.cancel_flag = threading.Event()
        
        self.start_button.config(state="disabled", text="正在生成...")
        self.progress_var.set(0)
        self.progress_label.config(text="正在初始化...")
        
        # 创建并启动新的工作线程
        self.current_task_thread = threading.Thread(
            target=self.generation_controller, 
            name="GenerationWorker"
        )
        # 不设置为守护线程，确保任务完成
        self.current_task_thread.daemon = False
        self.current_task_thread.start()
        
        # 显示取消按钮，隐藏开始按钮
        self.start_button.pack_forget()
        self.cancel_button.pack(side=tk.LEFT, padx=(5, 0))
    
    def cancel_generation(self):
        """取消当前正在运行的任务"""
        if hasattr(self, 'cancel_flag'):
            self.cancel_flag.set()
            logging.info("用户请求取消任务")
            self.progress_label.config(text="正在取消...")
            
            # 更新按钮状态（不禁用，显示取消中状态）
            self.cancel_button.config(text="取消中...", state="disabled")

    def generation_controller(self):
        """
        控制器方法：获取UI参数，验证并调用相应的后端配方函数。
        """
        try:
            # 检查取消标志
            if hasattr(self, 'cancel_flag') and self.cancel_flag.is_set():
                logging.info("任务被用户取消")
                return
            
            # 检查转换模式
            convert_mode = self.convert_mode_var.get()
            
            # 先获取基本参数
            recipe = self.recipe_var.get()
            params = {key: widget.get() for key, widget in self.paths.items()}
            params.update({key: widget.get() for key, widget in self.options.items()})
            
            if convert_mode == "selected":
                # 获取选中的文件
                if not self.selected_files:
                    messagebox.showwarning("警告", "请选择要转换的文件")
                    return
                
                # 获取选中文件的具体档号列表
                selected_file_numbers = []
                for index in self.selected_files:
                    if index < len(self.filtered_file_list):
                        file_number = self.filtered_file_list[index]['file_number']
                        selected_file_numbers.append(file_number)
                
                if selected_file_numbers:
                    logging.info(f"选择性转换模式：选中的档号 {selected_file_numbers}")
                    # 将选中的档号列表传递给生成器
                    params["selected_file_numbers"] = selected_file_numbers
                else:
                    messagebox.showwarning("警告", "未找到有效的选中文件")
                    return
            
            # 获取打印参数
            print_mode = self.print_mode_var.get()
            printer_name = self.printer_var.get() if print_mode in ["direct", "batch"] else None
            print_copies = int(self.print_copies_var.get()) if print_mode in ["direct", "batch"] else 1
            direct_print = print_mode == "direct"

            # 更新进度
            self.update_progress(10, "正在验证参数...")
            
            logging.info(f"任务开始: {recipe}")
            if direct_print and printer_name:
                logging.info(f"边转换边打印模式，打印机: {printer_name}，份数: {print_copies}")
            
            # 模拟参数验证过程
            self.update_progress(20, "正在加载文件...")

            if recipe == "全引目录":
                if not all(
                    [
                        params["jn_catalog_path"],
                        params["aj_catalog_path"],
                        params["template_path"],
                        params["output_folder"],
                    ]
                ):
                    messagebox.showerror(
                        "错误", "生成[全引目录]需要提供所有对应的文件和文件夹路径。"
                    )
                    return
                
                # 检查取消标志
                if hasattr(self, 'cancel_flag') and self.cancel_flag.is_set():
                    logging.info("任务被用户取消")
                    return
                    
                self.update_progress(30, "正在生成全引目录...")
                
                # 存储当前执行上下文，供辅助方法使用
                self._current_convert_mode = convert_mode
                self._current_selected_file_numbers = selected_file_numbers
                
                # 使用特性标志控制的生成执行
                if self.feature_manager.should_rollback("node_engine"):
                    # 强制使用传统实现
                    logging.info("Feature flag rollback: using legacy implementation only")
                    self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                elif self.feature_manager.should_use_shadow_mode("node_engine"):
                    # 影子模式：同时运行两种实现并验证
                    logging.info("Feature flag shadow mode: running both implementations")
                    with self.feature_manager.shadow_execution(
                        "node_engine",
                        lambda: self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies),
                        lambda: self._execute_node_based_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                    ) as result:
                        pass  # 结果已经通过影子执行处理
                elif self.feature_manager.is_enabled("node_engine"):
                    # 使用新的节点引擎
                    logging.info("Feature flag enabled: using node-based implementation")
                    self._execute_node_based_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                else:
                    # 使用传统实现（默认）
                    logging.info("Feature flag disabled: using legacy implementation")
                    self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
            elif recipe == "案卷目录":
                if not all(
                    [
                        params["aj_catalog_path"],
                        params["template_path"],
                        params["output_folder"],
                    ]
                ):
                    messagebox.showerror(
                        "错误", "生成[案卷目录]需要提供对应的文件和文件夹路径。"
                    )
                    return
                
                # 检查取消标志
                if hasattr(self, 'cancel_flag') and self.cancel_flag.is_set():
                    logging.info("任务被用户取消")
                    return
                    
                self.update_progress(30, "正在生成案卷目录...")
                
                # 存储当前执行上下文
                self._current_convert_mode = convert_mode
                self._current_selected_file_numbers = selected_file_numbers
                
                # 使用特性标志控制的生成执行
                if self.feature_manager.should_rollback("node_engine"):
                    logging.info("Feature flag rollback: using legacy implementation only")
                    self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                elif self.feature_manager.should_use_shadow_mode("node_engine"):
                    logging.info("Feature flag shadow mode: running both implementations")
                    with self.feature_manager.shadow_execution(
                        "node_engine",
                        lambda: self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies),
                        lambda: self._execute_node_based_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                    ) as result:
                        pass
                elif self.feature_manager.is_enabled("node_engine"):
                    logging.info("Feature flag enabled: using node-based implementation")
                    self._execute_node_based_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                else:
                    logging.info("Feature flag disabled: using legacy implementation")
                    self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
            elif recipe in ["卷内目录", "简化目录"]:
                # 根据不同的目录类型使用对应的路径
                if recipe == "卷内目录":
                    catalog_path_key = "jn_catalog_path"
                else:  # 简化目录
                    catalog_path_key = "jh_catalog_path"
                    
                if not all(
                    [
                        params[catalog_path_key],
                        params["template_path"],
                        params["output_folder"],
                    ]
                ):
                    messagebox.showerror(
                        "错误", f"生成[{recipe}]需要提供对应的文件和文件夹路径。"
                    )
                    return
                
                # 检查取消标志
                if hasattr(self, 'cancel_flag') and self.cancel_flag.is_set():
                    logging.info("任务被用户取消")
                    return
                    
                self.update_progress(30, f"正在生成{recipe}...")
                
                # 存储当前执行上下文
                self._current_convert_mode = convert_mode
                self._current_selected_file_numbers = selected_file_numbers
                
                # 使用特性标志控制的生成执行
                if self.feature_manager.should_rollback("node_engine"):
                    logging.info("Feature flag rollback: using legacy implementation only")
                    self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                elif self.feature_manager.should_use_shadow_mode("node_engine"):
                    logging.info("Feature flag shadow mode: running both implementations")
                    with self.feature_manager.shadow_execution(
                        "node_engine",
                        lambda: self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies),
                        lambda: self._execute_node_based_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                    ) as result:
                        pass
                elif self.feature_manager.is_enabled("node_engine"):
                    logging.info("Feature flag enabled: using node-based implementation")
                    self._execute_node_based_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
                else:
                    logging.info("Feature flag disabled: using legacy implementation")
                    self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)

            logging.info("任务成功完成！")
            
            # 更新进度显示
            self.progress_var.set(100)
            self.progress_label.config(text="任务完成！")
            
            # 显示性能统计
            try:
                calculator = get_height_calculator()
                stats = calculator.get_performance_stats()
                
                logging.info("=" * 40)
                logging.info("行高计算性能统计:")
                
                for method, data in stats.items():
                    if data['count'] > 0:
                        logging.info(f"{method.upper()}: {data['count']}次调用, "
                                   f"平均{data['avg_time']:.4f}秒/次, "
                                   f"总计{data['total_time']:.2f}秒")
                
                logging.info("=" * 40)
                
            except Exception as e:
                logging.warning(f"显示性能统计失败: {e}")

        except FileNotFoundError as e:
            error_msg = f"文件不存在: {e}"
            logging.error(error_msg)
            messagebox.showerror("文件错误", error_msg)
        except PermissionError as e:
            error_msg = f"文件权限不足: {e}"
            logging.error(error_msg)
            messagebox.showerror("权限错误", error_msg)
        except ValueError as e:
            error_msg = f"参数错误: {e}"
            logging.error(error_msg)
            messagebox.showerror("参数错误", error_msg)
        except ImportError as e:
            error_msg = f"模块导入失败: {e}\n请检查依赖项是否正确安装"
            logging.error(error_msg)
            messagebox.showerror("依赖错误", error_msg)
        except RuntimeError as e:
            error_msg = f"运行时错误: {e}"
            logging.error(error_msg)
            messagebox.showerror("运行错误", error_msg)
        except OSError as e:
            error_msg = f"系统操作失败: {e}"
            logging.error(error_msg)
            messagebox.showerror("系统错误", error_msg)
        except Exception as e:
            # 记录详细的错误信息用于调试
            import traceback
            error_details = traceback.format_exc()
            logging.error(f"未处理的异常: {error_details}")
            
            # 向用户显示简化的错误信息
            user_msg = f"发生意外错误，请检查日志获取详细信息\n错误类型: {type(e).__name__}"
            messagebox.showerror("意外错误", user_msg)
        finally:
            self.start_button.config(state="normal", text="开始生成")
            self.progress_var.set(0)
            self.progress_label.config(text="准备就绪")
            
            # 恢复按钮状态：隐藏取消按钮，显示开始按钮
            self.cancel_button.pack_forget()
            self.cancel_button.config(text="取消任务", state="normal")
            self.start_button.pack(side=tk.LEFT)
                
            # 清理取消标志
            if hasattr(self, 'cancel_flag'):
                del self.cancel_flag


    def _execute_legacy_generation(self, recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies):
        """执行传统的目录生成实现。"""
        if recipe == "全引目录":
            self._execute_full_index_legacy(params, direct_print, printer_name, print_copies)
        elif recipe == "案卷目录":
            self._execute_case_index_legacy(params, direct_print, printer_name, print_copies)
        elif recipe in ["卷内目录", "简化目录"]:
            self._execute_volume_index_legacy(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
    
    def _execute_node_based_generation(self, recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies):
        """执行基于节点引擎的目录生成实现（占位符）。"""
        logging.warning("Node-based implementation not yet available, falling back to legacy")
        # 目前回退到传统实现，后续会在Task 4中实现真正的节点执行
        self._execute_legacy_generation(recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies)
    
    def _execute_full_index_legacy(self, params, direct_print, printer_name, print_copies):
        """执行传统的全引目录生成。"""
        convert_mode = getattr(self, '_current_convert_mode', 'all')
        selected_file_numbers = getattr(self, '_current_selected_file_numbers', [])
        
        if convert_mode == "selected" and selected_file_numbers:
            for selected_file in selected_file_numbers:
                create_qy_full_index(
                    jn_catalog_path=params["jn_catalog_path"],
                    aj_catalog_path=params["aj_catalog_path"],
                    template_path=params["template_path"],
                    output_folder=params["output_folder"],
                    start_file=selected_file,
                    end_file=selected_file,
                    direct_print=direct_print,
                    printer_name=printer_name,
                    print_copies=print_copies,
                    cancel_flag=getattr(self, 'cancel_flag', None)
                )
        else:
            create_qy_full_index(
                jn_catalog_path=params["jn_catalog_path"],
                aj_catalog_path=params["aj_catalog_path"],
                template_path=params["template_path"],
                output_folder=params["output_folder"],
                start_file=params["start_file"],
                end_file=params["end_file"],
                direct_print=direct_print,
                printer_name=printer_name,
                print_copies=print_copies,
                cancel_flag=getattr(self, 'cancel_flag', None)
            )
    
    def _execute_case_index_legacy(self, params, direct_print, printer_name, print_copies):
        """执行传统的案卷目录生成。"""
        convert_mode = getattr(self, '_current_convert_mode', 'all')
        selected_file_numbers = getattr(self, '_current_selected_file_numbers', [])
        
        if convert_mode == "selected" and selected_file_numbers:
            for selected_file in selected_file_numbers:
                create_aj_index(
                    catalog_path=params["aj_catalog_path"],
                    template_path=params["template_path"],
                    output_folder=params["output_folder"],
                    start_file=selected_file,
                    end_file=selected_file,
                    direct_print=direct_print,
                    printer_name=printer_name,
                    print_copies=print_copies,
                    cancel_flag=getattr(self, 'cancel_flag', None)
                )
        else:
            create_aj_index(
                catalog_path=params["aj_catalog_path"],
                template_path=params["template_path"],
                output_folder=params["output_folder"],
                start_file=params["start_file"],
                end_file=params["end_file"],
                direct_print=direct_print,
                printer_name=printer_name,
                print_copies=print_copies,
                cancel_flag=getattr(self, 'cancel_flag', None)
            )
    
    def _execute_volume_index_legacy(self, recipe, params, convert_mode, selected_file_numbers, direct_print, printer_name, print_copies):
        """执行传统的卷内/简化目录生成。"""
        if recipe == "卷内目录":
            catalog_path_key = "jn_catalog_path"
        else:  # 简化目录
            catalog_path_key = "jh_catalog_path"
        
        if convert_mode == "selected" and selected_file_numbers:
            for selected_file in selected_file_numbers:
                create_jn_or_jh_index(
                    catalog_path=params[catalog_path_key],
                    template_path=params["template_path"],
                    output_folder=params["output_folder"],
                    recipe_name=recipe,
                    start_file=selected_file,
                    end_file=selected_file,
                    direct_print=direct_print,
                    printer_name=printer_name,
                    print_copies=print_copies,
                    cancel_flag=getattr(self, 'cancel_flag', None)
                )
        else:
            create_jn_or_jh_index(
                catalog_path=params[catalog_path_key],
                template_path=params["template_path"],
                output_folder=params["output_folder"],
                recipe_name=recipe,
                start_file=params["start_file"],
                end_file=params["end_file"],
                direct_print=direct_print,
                printer_name=printer_name,
                print_copies=print_copies,
                cancel_flag=getattr(self, 'cancel_flag', None)
            )


if __name__ == "__main__":
    app = DirectoryGeneratorGUI()
    app.mainloop()
