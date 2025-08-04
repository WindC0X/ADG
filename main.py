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
        
        self.title("统一目录生成器 v4.0 (Tkinter版)")
        
        # 从配置加载窗口几何
        geometry = self.config_manager.get_window_geometry()
        self.geometry(geometry)

        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[self.queue_handler],
        )

        self.create_widgets()
        self.load_config()  # 加载配置
        self.after(100, self.process_log_queue)
        
        # 初始化完成后显示当前方案信息
        self.after(200, self.show_initial_method_info)
        
        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """创建并布局所有的UI控件。"""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 目录类型选择 ---
        type_frame = ttk.LabelFrame(main_frame, text="1. 选择目录类型", padding="10")
        type_frame.pack(fill=tk.X, expand=True)
        self.recipe_var = tk.StringVar()
        self.recipe_combo = ttk.Combobox(
            type_frame,
            textvariable=self.recipe_var,
            values=["卷内目录", "案卷目录", "全引目录", "简化目录"],
            state="readonly",
        )
        self.recipe_combo.pack(fill=tk.X, expand=True)
        self.recipe_combo.current(0)

        # --- 行高计算方案选择 ---
        height_frame = ttk.LabelFrame(main_frame, text="2. 选择行高计算方案", padding="10")
        height_frame.pack(fill=tk.X, expand=True, pady=5)
        
        # 获取可用方案
        available_methods = get_available_methods()
        method_display_names = {
            'xlwings': 'xlwings (原始AutoFit，可能溢出)',
            'gdi': 'GDI (Windows精确测量，完美精度)',
            'pillow': 'Pillow (独立计算，高精度)'
        }
        
        method_values = [method_display_names.get(method, method) for method in available_methods]
        
        self.height_method_var = tk.StringVar()
        self.height_method_combo = ttk.Combobox(
            height_frame,
            textvariable=self.height_method_var,
            values=method_values,
            state="readonly",
        )
        self.height_method_combo.pack(fill=tk.X, expand=True)
        self.height_method_combo.current(0)  # 默认选择第一个（xlwings）
        
        # 绑定选择变化事件
        self.height_method_combo.bind('<<ComboboxSelected>>', self.on_height_method_changed)
        self.recipe_combo.bind('<<ComboboxSelected>>', self.on_recipe_changed)
        
        # 存储方案映射
        self.available_methods = available_methods
        self.method_display_names = method_display_names
        
        # 添加说明标签
        info_label = ttk.Label(
            height_frame, 
            text="提示：GDI方案精度最高，Pillow方案部署简单，xlwings方案速度最快",
            font=("", 8),
            foreground="gray"
        )
        info_label.pack(fill=tk.X, pady=(5, 0))

        # --- 路径配置 ---
        self.path_frame = ttk.LabelFrame(main_frame, text="3. 配置路径", padding="10")
        self.path_frame.pack(fill=tk.X, expand=True, pady=5)

        self.paths = {}
        self.path_widgets = {}  # 存储所有路径相关的控件
        
        # 创建路径网格容器
        self.path_grid = ttk.Frame(self.path_frame)
        self.path_grid.pack(fill=tk.X, expand=True)
        self.path_grid.columnconfigure(1, weight=1)

        # 定义所有可能的路径配置
        self.all_path_specs = {
            "jn_catalog_path": "卷内目录文件:",
            "aj_catalog_path": "案卷目录文件:",
            "jh_catalog_path": "简化目录文件:",
            "template_path": "模板文件:",
            "output_folder": "输出文件夹:",
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
        config_buttons_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(
            config_buttons_frame,
            text="清空当前路径",
            command=self.clear_current_paths
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            config_buttons_frame,
            text="重置配置",
            command=self.reset_config
        ).pack(side=tk.LEFT)

        # --- 可选参数 ---
        optional_frame = ttk.LabelFrame(main_frame, text="4. 可选参数", padding="10")
        optional_frame.pack(fill=tk.X, expand=True, pady=5)

        self.options = {}
        opt_grid = ttk.Frame(optional_frame)
        opt_grid.pack(fill=tk.X, expand=True)

        ttk.Label(opt_grid, text="起始档号/案卷号:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        self.options["start_file"] = ttk.Entry(opt_grid, width=30)
        self.options["start_file"].grid(row=0, column=1, padx=5, pady=2)
        self.options["start_file"].bind('<FocusOut>', lambda e: self.on_option_changed("start_file", e.widget.get()))

        ttk.Label(opt_grid, text="结束档号/案卷号:").grid(
            row=0, column=2, sticky=tk.W, padx=5, pady=2
        )
        self.options["end_file"] = ttk.Entry(opt_grid, width=30)
        self.options["end_file"].grid(row=0, column=3, padx=5, pady=2)
        self.options["end_file"].bind('<FocusOut>', lambda e: self.on_option_changed("end_file", e.widget.get()))

        # --- 控制与日志 ---
        control_frame = ttk.Frame(main_frame, padding="10")
        control_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.start_button = ttk.Button(
            control_frame, text="开始生成", command=self.run_generation_thread
        )
        self.start_button.pack(pady=5)

        log_frame = ttk.LabelFrame(control_frame, text="日志输出", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = ScrolledText(log_frame, state="disabled", height=15)
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
            entry = ttk.Entry(self.path_grid, width=70)
            entry.bind('<FocusOut>', lambda e, k=key: self.on_path_changed(k, e.widget.get()))
            
            # 创建浏览按钮
            is_dir = "folder" in key
            button = ttk.Button(
                self.path_grid,
                text="浏览...",
                command=lambda e=entry, d=is_dir, k=key: self.browse_path(e, d, k),
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
                widgets['label'].grid(row=current_row, column=0, sticky=tk.W, padx=5, pady=2)
                widgets['entry'].grid(row=current_row, column=1, sticky=tk.EW, padx=5, pady=2)
                widgets['button'].grid(row=current_row, column=2, sticky=tk.E, padx=5, pady=2)
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
            
            # 保存窗口几何信息
            geometry = self.geometry()
            self.config_manager.set_window_geometry(geometry)
            self.config_manager.save_config()
            
        except Exception as e:
            logging.warning(f"保存配置失败: {e}")
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
            while True:
                record = self.log_queue.get(block=False)
                self.log_text.configure(state="normal")
                self.log_text.insert(tk.END, record + "\n")
                self.log_text.configure(state="disabled")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)

    def run_generation_thread(self):
        """在单独的线程中启动目录生成任务，以防UI冻结。"""
        # 检查是否有任务正在运行
        if self.current_task_thread and self.current_task_thread.is_alive():
            messagebox.showwarning("任务进行中", "已有任务正在运行，请等待完成后再启动新任务")
            return
        
        self.start_button.config(state="disabled", text="正在生成...")
        
        # 创建并启动新的工作线程
        self.current_task_thread = threading.Thread(
            target=self.generation_controller, 
            name="GenerationWorker"
        )
        # 不设置为守护线程，确保任务完成
        self.current_task_thread.daemon = False
        self.current_task_thread.start()

    def generation_controller(self):
        """
        控制器方法：获取UI参数，验证并调用相应的后端配方函数。
        """
        try:
            recipe = self.recipe_var.get()
            params = {key: widget.get() for key, widget in self.paths.items()}
            params.update({key: widget.get() for key, widget in self.options.items()})

            logging.info(f"任务开始: {recipe}")

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
                create_qy_full_index(
                    jn_catalog_path=params["jn_catalog_path"],
                    aj_catalog_path=params["aj_catalog_path"],
                    template_path=params["template_path"],
                    output_folder=params["output_folder"],
                    start_file=params["start_file"],
                    end_file=params["end_file"],
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
                create_aj_index(
                    catalog_path=params["aj_catalog_path"],
                    template_path=params["template_path"],
                    output_folder=params["output_folder"],
                    start_file=params["start_file"],
                    end_file=params["end_file"],
                )
            elif recipe in ["卷内目录", "简化目录"]:
                if not all(
                    [
                        params["jh_catalog_path"],
                        params["template_path"],
                        params["output_folder"],
                    ]
                ):
                    messagebox.showerror(
                        "错误", f"生成[{recipe}]需要提供对应的文件和文件夹路径。"
                    )
                    return
                create_jn_or_jh_index(
                    catalog_path=params["jh_catalog_path"],
                    template_path=params["template_path"],
                    output_folder=params["output_folder"],
                    recipe_name=recipe,
                    start_file=params["start_file"],
                    end_file=params["end_file"],
                )

            logging.info("任务成功完成！")
            
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


if __name__ == "__main__":
    app = DirectoryGeneratorGUI()
    app.mainloop()
