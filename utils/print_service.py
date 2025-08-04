"""
打印服务模块 - 支持本地和网络打印机发现、批量打印、队列管理
"""
import logging
import queue
import threading
import time
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import win32print
import xlwings as xw


class PrinterError(Exception):
    """打印机相关错误"""
    pass


class PrintService:
    """
    企业级打印服务类
    支持打印机发现、批量打印、队列管理和错误恢复
    """
    
    def __init__(self):
        self.print_queue = queue.Queue()
        self.available_printers = []
        self.is_printing = False
        self.print_thread = None
        self.logger = logging.getLogger(__name__)
        
        # 关闭标志，用于优雅停止所有操作
        self.shutdown_flag = False
        
        # 异步打印线程池
        self.print_thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="PrintWorker")
        
        # 打印统计
        self.print_stats = {
            'total_submitted': 0,
            'total_completed': 0,
            'total_failed': 0
        }
        
        # 打印间隔控制
        self.printer_task_counters = {}  # 每台打印机的任务计数器
        self.printer_rest_states = {}    # 每台打印机的休息状态
        self.printer_rest_start_times = {}  # 每台打印机休息开始时间
        self.interval_config = None      # 间隔配置，由外部设置
        self._config_lock = threading.Lock()  # 配置锁
        
        # 初始化发现打印机
        self.refresh_printers()
    
    def refresh_printers(self) -> List[str]:
        """
        发现并刷新可用打印机列表（包括网络打印机）
        
        Returns:
            List[str]: 可用打印机名称列表
        """
        try:
            self.available_printers = []
            
            # 获取本地打印机
            local_printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)
            for printer in local_printers:
                self.available_printers.append(printer[2])
            
            # 获取网络打印机
            try:
                network_printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_NETWORK)
                for printer in network_printers:
                    self.available_printers.append(printer[2])
            except Exception as e:
                self.logger.warning(f"获取网络打印机失败: {e}")
            
            # 获取连接的打印机
            try:
                connected_printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_CONNECTIONS)
                for printer in connected_printers:
                    if printer[2] not in self.available_printers:
                        self.available_printers.append(printer[2])
            except Exception as e:
                self.logger.warning(f"获取连接打印机失败: {e}")
            
            self.logger.info(f"发现 {len(self.available_printers)} 台打印机")
            return self.available_printers
            
        except Exception as e:
            self.logger.error(f"打印机发现失败: {e}")
            return []
    
    def get_default_printer(self) -> Optional[str]:
        """
        获取系统默认打印机
        
        Returns:
            Optional[str]: 默认打印机名称，如果没有则返回None
        """
        try:
            return win32print.GetDefaultPrinter()
        except Exception as e:
            self.logger.warning(f"获取默认打印机失败: {e}")
            return None
    
    def check_printer_status(self, printer_name: str) -> bool:
        """
        检查打印机是否在线可用
        
        Args:
            printer_name (str): 打印机名称
            
        Returns:
            bool: 打印机是否可用
        """
        try:
            handle = win32print.OpenPrinter(printer_name)
            printer_info = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)
            
            # 检查打印机状态 - 0表示正常
            status = printer_info['Status']
            return status == 0
            
        except Exception as e:
            self.logger.warning(f"检查打印机 {printer_name} 状态失败: {e}")
            return False
    
    def print_excel_file(self, file_path: str, printer_name: str, copies: int = 1) -> bool:
        """
        打印Excel文件
        
        Args:
            file_path (str): Excel文件路径
            printer_name (str): 打印机名称
            copies (int): 打印份数
            
        Returns:
            bool: 打印是否成功
        """
        app = None
        wb = None
        
        try:
            # 检查打印机状态
            if not self.check_printer_status(printer_name):
                raise PrinterError(f"打印机 {printer_name} 不可用")
            
            # 使用xlwings打开文件并打印
            app = xw.App(visible=False)
            wb = app.books.open(file_path)
            
            # 设置打印参数
            for ws in wb.sheets:
                ws.api.PrintOut(
                    ActivePrinter=printer_name,
                    Copies=copies,
                    Preview=False
                )
            
            self.logger.info(f"成功打印文件: {file_path} 到 {printer_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"打印失败 {file_path}: {e}")
            return False
            
        finally:
            # 清理资源
            if wb:
                wb.close()
            if app:
                app.quit()
    
    def async_print(self, file_path: str, printer_name: str, copies: int = 1):
        """
        异步打印 - 立即返回，不阻塞转换过程
        
        Args:
            file_path (str): Excel文件路径
            printer_name (str): 打印机名称
            copies (int): 打印份数
            
        Returns:
            concurrent.futures.Future: 异步任务对象
        """
        self.print_stats['total_submitted'] += 1
        
        print_job = {
            'file_path': file_path,
            'printer_name': printer_name,
            'copies': copies,
            'timestamp': time.time(),
            'job_id': self.print_stats['total_submitted']
        }
        
        # 提交到线程池异步执行
        future = self.print_thread_pool.submit(self._execute_async_print, print_job)
        self.logger.info(f"已提交异步打印任务 [{print_job['job_id']}]: {file_path} -> {printer_name}")
        return future
    
    def _execute_async_print(self, print_job):
        """
        执行异步打印任务的内部方法
        
        Args:
            print_job (dict): 打印任务信息
            
        Returns:
            bool: 打印是否成功
        """
        job_id = print_job['job_id']
        printer_name = print_job['printer_name']
        
        try:
            # 检查是否已被关闭
            if self.shutdown_flag:
                self.logger.info(f"服务已关闭，取消打印任务 [{job_id}]: {print_job['file_path']}")
                return False
            
            self.logger.info(f"开始执行异步打印任务 [{job_id}]: {print_job['file_path']}")
            
            # 检查打印机是否在休息
            while self._is_printer_resting(printer_name) and not self.shutdown_flag:
                rest_info = self.get_printer_rest_info(printer_name)
                self.logger.info(f"打印机 {printer_name} 正在休息，剩余 {rest_info['remaining_seconds']} 秒")
                time.sleep(1)  # 每秒检查一次
            
            # 再次检查关闭标志
            if self.shutdown_flag:
                self.logger.info(f"服务已关闭，取消打印任务 [{job_id}]: {print_job['file_path']}")
                return False
            
            # 执行打印
            success = self.robust_print(
                print_job['file_path'],
                print_job['printer_name'], 
                print_job['copies']
            )
            
            if success:
                self.print_stats['total_completed'] += 1
                
                # 增加打印机任务计数器（仅在成功时）
                if printer_name not in self.printer_task_counters:
                    self.printer_task_counters[printer_name] = 0
                self.printer_task_counters[printer_name] += 1
                
                self.logger.info(f"异步打印完成 [{job_id}] ({self.print_stats['total_completed']}/{self.print_stats['total_submitted']}): {print_job['file_path']}")
                self.logger.info(f"打印机 {printer_name} 当前任务计数: {self.printer_task_counters[printer_name]}")
                
                # 检查是否需要触发休息
                if self._should_trigger_rest(printer_name):
                    self._start_printer_rest(printer_name)
                
            else:
                self.print_stats['total_failed'] += 1
                self.logger.error(f"异步打印失败 [{job_id}]: {print_job['file_path']}")
                
            return success
            
        except Exception as e:
            self.print_stats['total_failed'] += 1
            self.logger.error(f"异步打印异常 [{job_id}]: {print_job['file_path']} - {e}")
            return False
    
    def get_pending_print_count(self) -> int:
        """
        获取待打印任务数量
        
        Returns:
            int: 待处理的打印任务数量
        """
        try:
            # 获取线程池中活跃线程数量
            return len([t for t in self.print_thread_pool._threads if t.is_alive()]) if hasattr(self.print_thread_pool, '_threads') else 0
        except:
            return 0
    
    def get_print_stats(self) -> Dict[str, int]:
        """
        获取打印统计信息
        
        Returns:
            Dict[str, int]: 包含提交、完成、失败数量的统计信息
        """
        return self.print_stats.copy()
    
    def set_interval_config(self, config: Dict[str, Any]):
        """
        设置打印间隔配置
        
        Args:
            config (Dict[str, Any]): 包含enabled、task_count、interval_seconds的配置
        """
        with self._config_lock:
            self.interval_config = config.copy()
            self.logger.info(f"打印间隔配置已更新: {config}")
    
    def get_interval_config(self) -> Dict[str, Any]:
        """
        获取当前打印间隔配置
        
        Returns:
            Dict[str, Any]: 间隔配置
        """
        with self._config_lock:
            return self.interval_config.copy() if self.interval_config else None
    
    def _should_trigger_rest(self, printer_name: str) -> bool:
        """
        检查是否应该触发休息
        
        Args:
            printer_name (str): 打印机名称
            
        Returns:
            bool: 是否应该触发休息
        """
        with self._config_lock:
            if not self.interval_config or not self.interval_config.get('enabled', True):
                return False
            
            task_count = self.printer_task_counters.get(printer_name, 0)
            threshold = self.interval_config.get('task_count', 3)
            
            return task_count >= threshold
    
    def _is_printer_resting(self, printer_name: str) -> bool:
        """
        检查打印机是否正在休息
        
        Args:
            printer_name (str): 打印机名称
            
        Returns:
            bool: 是否正在休息
        """
        if printer_name not in self.printer_rest_states:
            return False
        
        if not self.printer_rest_states[printer_name]:
            return False
        
        # 检查休息时间是否已到
        with self._config_lock:
            if not self.interval_config:
                return False
            
            start_time = self.printer_rest_start_times.get(printer_name, 0)
            interval_seconds = self.interval_config.get('interval_seconds', 50)
            
            if time.time() - start_time >= interval_seconds:
                # 休息时间到，重置状态
                self.printer_rest_states[printer_name] = False
                self.printer_task_counters[printer_name] = 0
                self.logger.info(f"打印机 {printer_name} 休息结束，重置任务计数器")
                return False
        
        return True
    
    def _start_printer_rest(self, printer_name: str):
        """
        开始打印机休息
        
        Args:
            printer_name (str): 打印机名称
        """
        self.printer_rest_states[printer_name] = True
        self.printer_rest_start_times[printer_name] = time.time()
        
        with self._config_lock:
            interval_seconds = self.interval_config.get('interval_seconds', 50) if self.interval_config else 50
        
        self.logger.info(f"打印机 {printer_name} 开始休息 {interval_seconds} 秒")
    
    def skip_printer_rest(self, printer_name: str) -> bool:
        """
        手动跳过打印机休息
        
        Args:
            printer_name (str): 打印机名称
            
        Returns:
            bool: 是否成功跳过
        """
        if printer_name in self.printer_rest_states and self.printer_rest_states[printer_name]:
            self.printer_rest_states[printer_name] = False
            self.printer_task_counters[printer_name] = 0
            self.logger.info(f"用户手动跳过打印机 {printer_name} 的休息时间")
            return True
        return False
    
    def get_printer_rest_info(self, printer_name: str) -> Dict[str, Any]:
        """
        获取打印机休息信息
        
        Args:
            printer_name (str): 打印机名称
            
        Returns:
            Dict[str, Any]: 包含是否休息、剩余时间等信息
        """
        if not self._is_printer_resting(printer_name):
            return {
                'is_resting': False,
                'remaining_seconds': 0,
                'task_count': self.printer_task_counters.get(printer_name, 0)
            }
        
        start_time = self.printer_rest_start_times.get(printer_name, 0)
        with self._config_lock:
            interval_seconds = self.interval_config.get('interval_seconds', 50) if self.interval_config else 50
        
        elapsed = time.time() - start_time
        remaining = max(0, interval_seconds - elapsed)
        
        return {
            'is_resting': True,
            'remaining_seconds': int(remaining),
            'task_count': self.printer_task_counters.get(printer_name, 0)
        }
    
    def wait_for_all_prints(self, timeout: Optional[float] = None):
        """
        等待所有异步打印任务完成
        
        Args:
            timeout (Optional[float]): 超时时间（秒），None表示无限等待
        """
        try:
            self.print_thread_pool.shutdown(wait=True, timeout=timeout)
            self.logger.info("所有异步打印任务已完成")
        except Exception as e:
            self.logger.warning(f"等待打印任务完成时异常: {e}")
    
    def shutdown(self, timeout: Optional[float] = 5.0):
        """
        强制关闭打印服务和所有线程
        
        Args:
            timeout (Optional[float]): 等待超时时间（秒），默认5秒
        """
        try:
            self.logger.info("正在关闭打印服务...")
            
            # 设置关闭标志，阻止新任务开始
            self.shutdown_flag = True
            
            # 停止批量打印
            self.stop_batch_printing()
            
            # 关闭线程池，强制终止所有任务
            self.print_thread_pool.shutdown(wait=False)
            
            # 等待一段时间让任务自然结束
            if timeout:
                import concurrent.futures
                try:
                    # 等待所有futures完成或超时
                    concurrent.futures.wait(
                        [future for future in getattr(self.print_thread_pool, '_futures', [])],
                        timeout=timeout,
                        return_when=concurrent.futures.ALL_COMPLETED
                    )
                except:
                    pass
            
            self.logger.info("打印服务已关闭")
            
        except Exception as e:
            self.logger.warning(f"关闭打印服务时发生异常: {e}")
            
        finally:
            # 强制关闭，不等待
            try:
                self.print_thread_pool.shutdown(wait=False)
            except:
                pass

    def robust_print(self, file_path: str, printer_name: str, copies: int = 1, max_retries: int = 3) -> bool:
        """
        稳定的打印功能，支持重试机制
        
        Args:
            file_path (str): Excel文件路径
            printer_name (str): 打印机名称
            copies (int): 打印份数
            max_retries (int): 最大重试次数
            
        Returns:
            bool: 打印是否成功
        """
        for attempt in range(max_retries):
            try:
                # 检查是否已被关闭
                if self.shutdown_flag:
                    self.logger.info(f"服务已关闭，停止打印重试: {file_path}")
                    return False
                
                if self.print_excel_file(file_path, printer_name, copies):
                    return True
                    
                if attempt < max_retries - 1:
                    self.logger.warning(f"打印尝试 {attempt + 1} 失败，2秒后重试...")
                    time.sleep(2)
                    
            except Exception as e:
                self.logger.warning(f"打印尝试 {attempt + 1} 异常: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        raise PrinterError(f"打印文件 {file_path} 到 {printer_name} 失败，已重试 {max_retries} 次")
    
    def add_print_job(self, file_path: str, printer_name: str, copies: int = 1):
        """
        添加打印任务到队列
        
        Args:
            file_path (str): 文件路径
            printer_name (str): 打印机名称
            copies (int): 打印份数
        """
        job = {
            'file_path': file_path,
            'printer_name': printer_name,
            'copies': copies,
            'timestamp': time.time()
        }
        self.print_queue.put(job)
        self.logger.info(f"添加打印任务: {file_path} -> {printer_name}")
    
    def start_batch_printing(self):
        """
        启动批量打印处理线程
        """
        if self.is_printing:
            self.logger.warning("批量打印已在进行中")
            return
        
        self.is_printing = True
        self.print_thread = threading.Thread(target=self._process_print_queue, daemon=True)
        self.print_thread.start()
        self.logger.info("批量打印线程已启动")
    
    def stop_batch_printing(self):
        """
        停止批量打印
        """
        self.is_printing = False
        if self.print_thread and self.print_thread.is_alive():
            self.print_thread.join(timeout=5)
        self.logger.info("批量打印已停止")
    
    def _process_print_queue(self):
        """
        处理打印队列的内部方法
        """
        while self.is_printing or not self.print_queue.empty():
            try:
                # 获取打印任务，超时1秒
                job = self.print_queue.get(timeout=1)
                
                self.logger.info(f"开始处理打印任务: {job['file_path']}")
                
                success = self.robust_print(
                    job['file_path'],
                    job['printer_name'],
                    job['copies']
                )
                
                if success:
                    self.logger.info(f"打印任务完成: {job['file_path']}")
                else:
                    self.logger.error(f"打印任务失败: {job['file_path']}")
                
                self.print_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                self.logger.error(f"处理打印队列异常: {e}")
    
    def get_queue_size(self) -> int:
        """
        获取当前队列大小
        
        Returns:
            int: 队列中等待的任务数量
        """
        return self.print_queue.qsize()
    
    def clear_queue(self):
        """
        清空打印队列
        """
        with self.print_queue.mutex:
            self.print_queue.queue.clear()
        self.logger.info("打印队列已清空")


# 单例模式的全局打印服务实例
_print_service_instance = None

def get_print_service() -> PrintService:
    """
    获取全局打印服务实例（单例模式）
    
    Returns:
        PrintService: 打印服务实例
    """
    global _print_service_instance
    if _print_service_instance is None:
        _print_service_instance = PrintService()
    return _print_service_instance

def cleanup_print_service():
    """
    清理全局打印服务实例
    """
    global _print_service_instance
    if _print_service_instance is not None:
        try:
            _print_service_instance.shutdown(timeout=2.0)
        except:
            pass
        finally:
            _print_service_instance = None


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    print("=== 打印服务测试 ===")
    service = PrintService()
    
    print(f"发现打印机: {service.available_printers}")
    print(f"默认打印机: {service.get_default_printer()}")
    
    if service.available_printers:
        test_printer = service.available_printers[0]
        print(f"测试打印机状态: {test_printer} -> {service.check_printer_status(test_printer)}")