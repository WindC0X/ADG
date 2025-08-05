import logging
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import sys
import os

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


class QueueHandler(logging.Handler):
    """
    一个自定义的日志处理器，将日志记录发送到一个队列中，
    以便在GUI线程中安全地更新Text控件。
    """

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class DirectoryGeneratorGUI(tk.Tk):
    """
    Tkinter图形用户界面主应用类。
    """

    def __init__(self):
        super().__init__()
        
        # 初始化配置管理器
        self.config_manager = get_config_manager()
        
        # 初始化线程管理
        self.current_task_thread = None
        self.shutdown_flag = threading.Event()
        
        # 初始化打印服务
        from utils.print_service import get_print_service
        self.print_service = get_print_service()
        
        self.title("统一目录生成器 v4.0 (Tkinter版)")
        
        # 从配置加载窗口几何
        geometry = self.config_manager.get_window_geometry()
        self.geometry(geometry)

        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
            datefmt="%H:%M:%S",
            handlers=[self.queue_handler],
        )

        self.create_widgets()
        self.load_config()  # 加载配置
        self.refresh_printers()  # 初始化打印机列表
        self.after(100, self.process_log_queue)
        
        # 初始化完成后显示当前方案信息
        self.after(200, self.show_initial_method_info)
        
        # 启动打印状态监控
        self.after(1000, self.monitor_print_status)
        
        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """创建并布局所有的UI控件。"""
        main_frame = ttk.Frame(self, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 顶部紧凑配置区域 ---
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, expand=False, pady=(0, 1))
        
        # 第一行：目录类型、行高方案、档号范围
        config_row1 = ttk.Frame(top_frame)
        config_row1.pack(fill=tk.X, pady=(0, 1))
        
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
        self.recipe_combo.pack(side=tk.LEFT, padx=(2, 8))
        self.recipe_combo.current(0)

        # 行高方案
        ttk.Label(config_row1, text="行高方案:").pack(side=tk.LEFT)
        height_container = ttk.Frame(config_row1)
        height_container.pack(side=tk.LEFT, padx=(2, 8))
        
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
        self.options["start_file"].pack(side=tk.LEFT, padx=(2, 8))
        self.options["start_file"].bind('<FocusOut>', lambda e: self.on_option_changed("start_file", e.widget.get()))

        ttk.Label(config_row1, text="结束档号:").pack(side=tk.LEFT)
        self.options["end_file"] = ttk.Entry(config_row1, width=8)
        self.options["end_file"].pack(side=tk.LEFT, padx=(2, 0))
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

        # 左侧：打印设置和控制按钮
        left_control = ttk.Frame(control_frame)
        left_control.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        
        # 打印设置区域
        print_frame = ttk.LabelFrame(left_control, text="打印设置", padding="1")
        print_frame.pack(fill=tk.X, expand=False, pady=(0, 1))
        
        # 打印模式选择
        mode_frame = ttk.Frame(print_frame)
        mode_frame.pack(fill=tk.X, pady=1)
        
        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.print_mode_var = tk.StringVar(value="none")
        self.print_mode_var.trace('w', self.on_print_mode_changed)
        ttk.Radiobutton(mode_frame, text="不打印", variable=self.print_mode_var, value="none").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_frame, text="直接打印", variable=self.print_mode_var, value="direct").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_frame, text="批量打印", variable=self.print_mode_var, value="batch").pack(side=tk.LEFT, padx=2)
        
        # 打印机选择
        printer_frame = ttk.Frame(print_frame)
        printer_frame.pack(fill=tk.X, pady=0)
        
        ttk.Label(printer_frame, text="打印机:").pack(side=tk.LEFT, padx=(0, 3))
        
        self.printer_var = tk.StringVar()
        self.printer_combo = ttk.Combobox(printer_frame, textvariable=self.printer_var, width=15, state="readonly")
        self.printer_combo.pack(side=tk.LEFT, padx=1)
        
        # 刷新打印机按钮
        self.refresh_printer_btn = ttk.Button(printer_frame, text="刷新", command=self.refresh_printers, width=6)
        self.refresh_printer_btn.pack(side=tk.LEFT, padx=1)
        
        # 打印份数
        copies_frame = ttk.Frame(print_frame)
        copies_frame.pack(fill=tk.X, pady=0)
        
        ttk.Label(copies_frame, text="份数:").pack(side=tk.LEFT, padx=(0, 3))
        
        self.print_copies_var = tk.StringVar(value="1")
        copies_spinbox = ttk.Spinbox(copies_frame, from_=1, to=10, width=4, textvariable=self.print_copies_var)
        copies_spinbox.pack(side=tk.LEFT, padx=1)
        
        # 批量打印按钮
        self.batch_print_btn = ttk.Button(print_frame, text="批量打印", command=self.batch_print_files, state="disabled")
        self.batch_print_btn.pack(pady=1)
        
        # 打印状态显示
        status_frame = ttk.Frame(print_frame)
        status_frame.pack(fill=tk.X, pady=1)
        
        self.print_status_var = tk.StringVar(value="队列: 0 | 完成: 0 | 失败: 0")
        self.print_status_label = ttk.Label(status_frame, textvariable=self.print_status_var, font=("Arial", 8))
        self.print_status_label.pack(side=tk.LEFT)
        
        # 打印间隔控制（折叠式）
        interval_frame = ttk.LabelFrame(print_frame, text="间隔控制", padding="2")
        interval_frame.pack(fill=tk.X, pady=0)
        
        # 第一行：启用开关和任务数设置
        interval_top_frame = ttk.Frame(interval_frame)
        interval_top_frame.pack(fill=tk.X, pady=0)
        
        self.interval_enabled_var = tk.BooleanVar(value=True)
        interval_checkbox = ttk.Checkbutton(
            interval_top_frame, 
            text="启用", 
            variable=self.interval_enabled_var,
            command=self.on_interval_settings_changed
        )
        interval_checkbox.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(interval_top_frame, text="每").pack(side=tk.LEFT)
        
        self.interval_task_count_var = tk.StringVar(value="3")
        task_count_spinbox = ttk.Spinbox(
            interval_top_frame, 
            from_=1, 
            to=20, 
            width=2, 
            textvariable=self.interval_task_count_var,
            command=self.on_interval_settings_changed
        )
        task_count_spinbox.pack(side=tk.LEFT, padx=(0, 0))
        task_count_spinbox.bind('<KeyRelease>', lambda e: self.on_interval_settings_changed())
        
        ttk.Label(interval_top_frame, text="个任务休息").pack(side=tk.LEFT)
        
        self.interval_seconds_var = tk.StringVar(value="50")
        seconds_spinbox = ttk.Spinbox(
            interval_top_frame, 
            from_=10, 
            to=300, 
            width=2, 
            textvariable=self.interval_seconds_var,
            command=self.on_interval_settings_changed
        )
        seconds_spinbox.pack(side=tk.LEFT, padx=(0, 0))
        seconds_spinbox.bind('<KeyRelease>', lambda e: self.on_interval_settings_changed())
        
        ttk.Label(interval_top_frame, text="秒").pack(side=tk.LEFT)
        
        # 跳过休息按钮
        self.skip_rest_btn = ttk.Button(
            interval_top_frame, 
            text="跳过", 
            command=self.skip_printer_rest,
            state="disabled",
            width=5
        )
        self.skip_rest_btn.pack(side=tk.RIGHT, padx=1)
        
        # 间隔状态显示
        self.interval_status_var = tk.StringVar() 
        self.interval_status_label = ttk.Label(print_frame, textvariable=self.interval_status_var, font=("Arial", 8), foreground="blue")
        self.interval_status_label.pack(fill=tk.X, pady=0)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            left_control, 
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            length=180
        )
        self.progress_bar.pack(pady=(0, 1))
        
        # 进度标签
        self.progress_label = ttk.Label(left_control, text="准备就绪", font=("Arial", 8))
        self.progress_label.pack(pady=(0, 1))
        
        # 开始按钮
        self.start_button = ttk.Button(
            left_control, text="开始生成", command=self.run_generation_thread, width=12
        )
        self.start_button.pack(pady=1)

        # 右侧：日志输出
        log_frame = ttk.LabelFrame(control_frame, text="日志", padding="1")
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(1, 0))
        self.log_text = ScrolledText(log_frame, state="disabled", height=6, width=40, wrap=tk.WORD)
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

    def on_option_changed(self, option_key, option_value):
        """当可选参数改变时的回调函数"""
        self.config_manager.set_option(option_key, option_value)
        self.config_manager.save_config()

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

    def process_log_queue(self):
        """从队列中获取日志消息并显示在文本控件中。"""
        try:
            batch_size = 10  # 批量处理，减少UI更新频率
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
        self.after(200, self.process_log_queue)  # 降低更新频率

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
        
        # 添加取消按钮
        if hasattr(self, 'cancel_button'):
            self.cancel_button.pack(side=tk.LEFT, padx=2)
        else:
            self.cancel_button = ttk.Button(
                self, 
                text="取消", 
                command=self.cancel_generation,
                width=8
            )
            self.cancel_button.pack(side=tk.LEFT, padx=2)
    
    def cancel_generation(self):
        """取消当前正在运行的任务"""
        if hasattr(self, 'cancel_flag'):
            self.cancel_flag.set()
            logging.info("用户请求取消任务")
            self.progress_label.config(text="正在取消...")
            
            # 禁用取消按钮
            if hasattr(self, 'cancel_button'):
                self.cancel_button.config(state="disabled")

    def generation_controller(self):
        """
        控制器方法：获取UI参数，验证并调用相应的后端配方函数。
        """
        try:
            # 检查取消标志
            if hasattr(self, 'cancel_flag') and self.cancel_flag.is_set():
                logging.info("任务被用户取消")
                return
                
            recipe = self.recipe_var.get()
            params = {key: widget.get() for key, widget in self.paths.items()}
            params.update({key: widget.get() for key, widget in self.options.items()})

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
            
            # 移除取消按钮
            if hasattr(self, 'cancel_button'):
                self.cancel_button.pack_forget()
                
            # 清理取消标志
            if hasattr(self, 'cancel_flag'):
                del self.cancel_flag


if __name__ == "__main__":
    app = DirectoryGeneratorGUI()
    app.mainloop()
