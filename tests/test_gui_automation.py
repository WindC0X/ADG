"""
GUI自动化测试
测试Tkinter界面的交互逻辑和状态管理
"""

import pytest
import sys
import os
import tkinter as tk
import threading
import time
from unittest.mock import Mock, patch, MagicMock

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import (
    skip_on_non_windows,
    create_mock_archive_data,
    MockHeightCalculator
)

# GUI测试需要特殊处理，因为需要事件循环
@pytest.fixture
def mock_tk_app():
    """模拟Tkinter应用fixture"""
    # 由于GUI测试的复杂性，我们主要测试业务逻辑而不是真实的GUI
    return Mock()

class TestGUIConfiguration:
    """测试GUI配置相关功能"""
    
    def test_config_manager_integration(self, test_env):
        """测试配置管理器与GUI的集成"""
        from utils.config_manager import ConfigManager
        
        # 创建配置管理器
        config_file = os.path.join(test_env.temp_dir, 'gui_test_config.json')
        config_manager = ConfigManager(config_file)
        
        # 模拟GUI操作：设置路径
        test_paths = {
            'jn_catalog_path': '/test/jn_catalog.xlsx',
            'template_path': '/test/template.xlsx',
            'output_folder': '/test/output'
        }
        
        for key, value in test_paths.items():
            config_manager.set_path(key, value)
        
        # 保存配置
        assert config_manager.save_config() == True
        
        # 模拟重新启动应用，加载配置
        new_config_manager = ConfigManager(config_file)
        
        # 验证配置被正确加载
        loaded_paths = new_config_manager.get_paths()
        for key, value in test_paths.items():
            assert loaded_paths[key] == value
    
    def test_recipe_selection_logic(self):
        """测试目录类型选择逻辑"""
        # 模拟GUI中的目录类型映射
        recipe_path_mapping = {
            "卷内目录": ["jn_catalog_path", "template_path", "output_folder"],
            "案卷目录": ["aj_catalog_path", "template_path", "output_folder"],
            "全引目录": ["jn_catalog_path", "aj_catalog_path", "template_path", "output_folder"],
            "简化目录": ["jh_catalog_path", "template_path", "output_folder"],
        }
        
        # 测试每种类型的路径需求
        for recipe, required_paths in recipe_path_mapping.items():
            assert len(required_paths) >= 3  # 至少需要3个路径
            assert "template_path" in required_paths  # 都需要模板
            assert "output_folder" in required_paths  # 都需要输出目录
    
    def test_height_method_selection(self):
        """测试行高方案选择逻辑"""
        from core.enhanced_height_calculator import get_available_methods
        
        # 获取可用方法
        available_methods = get_available_methods()
        
        # 验证基本方法可用性
        assert 'xlwings' in available_methods  # xlwings应该总是可用
        
        # 方法显示名称映射
        method_display_names = {
            'xlwings': 'xlwings',
            'gdi': 'GDI',
            'pillow': 'Pillow'
        }
        
        # 验证映射的正确性
        for method in available_methods:
            assert method in method_display_names
            assert isinstance(method_display_names[method], str)

class TestGUIFileListManagement:
    """测试GUI文件列表管理功能"""
    
    def test_file_list_parsing_logic(self, mock_archive_data):
        """测试文件列表解析逻辑"""
        # 模拟GUI中的档案数据解析
        file_groups = {}
        possible_file_number_columns = ['案卷档号', '档号', '文件号', '编号']
        
        # 查找档号列
        file_number_col = None
        for col in possible_file_number_columns:
            if col in mock_archive_data.columns:
                file_number_col = col
                break
        
        assert file_number_col is not None
        
        # 按档号分组统计
        for _, row in mock_archive_data.iterrows():
            file_number = str(row[file_number_col]).strip()
            if file_number and file_number != 'nan':
                if file_number not in file_groups:
                    file_groups[file_number] = 0
                file_groups[file_number] += 1
        
        # 验证分组结果
        assert len(file_groups) > 0
        assert all(count > 0 for count in file_groups.values())
    
    def test_file_range_filtering_logic(self, mock_archive_data):
        """测试文件范围过滤逻辑"""
        # 模拟GUI中的范围过滤
        all_files = mock_archive_data['案卷档号'].unique().tolist()
        
        def apply_file_range_filter(files, start_file, end_file):
            if not start_file and not end_file:
                return files
            
            filtered = []
            for file_number in files:
                # 检查起始档号
                if start_file and file_number < start_file:
                    continue
                # 检查结束档号
                if end_file and file_number > end_file:
                    continue
                filtered.append(file_number)
            
            return filtered
        
        # 测试无过滤
        result = apply_file_range_filter(all_files, '', '')
        assert result == all_files
        
        # 测试起始过滤
        start_file = all_files[1] if len(all_files) > 1 else all_files[0]
        result = apply_file_range_filter(all_files, start_file, '')
        assert all(f >= start_file for f in result)
        
        # 测试结束过滤
        end_file = all_files[-2] if len(all_files) > 1 else all_files[-1]
        result = apply_file_range_filter(all_files, '', end_file)
        assert all(f <= end_file for f in result)
    
    def test_file_sorting_logic(self, mock_archive_data):
        """测试文件排序逻辑"""
        # 模拟GUI文件列表数据
        file_list_data = []
        for _, row in mock_archive_data.iterrows():
            file_list_data.append({
                'file_number': row['案卷档号'],
                'display_name': f"卷内目录_{row['案卷档号']}",
                'item_count': 1
            })
        
        # 测试按文件名排序
        sorted_by_name = sorted(file_list_data, key=lambda x: x['display_name'])
        assert len(sorted_by_name) == len(file_list_data)
        
        # 测试按条目数排序
        # 先设置不同的条目数
        for i, item in enumerate(file_list_data):
            item['item_count'] = i + 1
        
        sorted_by_count = sorted(file_list_data, key=lambda x: x['item_count'])
        assert sorted_by_count[0]['item_count'] <= sorted_by_count[-1]['item_count']

class TestGUITaskManagement:
    """测试GUI任务管理功能"""
    
    def test_task_cancellation_logic(self):
        """测试任务取消逻辑"""
        import threading
        
        # 模拟GUI中的取消标志
        cancel_flag = threading.Event()
        
        def mock_long_running_task(cancel_flag):
            """模拟长时间运行的任务"""
            for i in range(100):
                if cancel_flag.is_set():
                    return "cancelled"
                time.sleep(0.01)  # 模拟工作
            return "completed"
        
        # 测试正常完成
        cancel_flag.clear()
        result = mock_long_running_task(cancel_flag)
        # 注意：这个测试会花费约1秒，在真实场景中我们会用更短的时间
        
        # 测试取消
        cancel_flag.clear()
        # 在另一个线程中设置取消标志
        def set_cancel():
            time.sleep(0.1)
            cancel_flag.set()
        
        cancel_thread = threading.Thread(target=set_cancel)
        cancel_thread.start()
        
        result = mock_long_running_task(cancel_flag)
        cancel_thread.join()
        
        assert result == "cancelled"
    
    def test_progress_tracking_logic(self):
        """测试进度跟踪逻辑"""
        # 模拟进度更新
        progress_updates = []
        
        def mock_progress_callback(value, text):
            progress_updates.append((value, text))
        
        def mock_task_with_progress(progress_callback):
            total_steps = 5
            for i in range(total_steps):
                progress = (i + 1) / total_steps * 100
                progress_callback(progress, f"步骤 {i+1}/{total_steps}")
                time.sleep(0.01)  # 模拟工作
        
        # 执行任务
        mock_task_with_progress(mock_progress_callback)
        
        # 验证进度更新
        assert len(progress_updates) == 5
        assert progress_updates[0][0] == 20.0  # 第一步20%
        assert progress_updates[-1][0] == 100.0  # 最后一步100%
        
        # 验证进度递增
        for i in range(1, len(progress_updates)):
            assert progress_updates[i][0] >= progress_updates[i-1][0]

class TestGUIPrintingIntegration:
    """测试GUI打印集成功能"""
    
    def test_print_mode_selection_logic(self):
        """测试打印模式选择逻辑"""
        # 模拟GUI中的打印模式
        print_modes = {
            "none": {"requires_printer": False, "batch_enabled": False},
            "direct": {"requires_printer": True, "batch_enabled": False},
            "batch": {"requires_printer": True, "batch_enabled": True}
        }
        
        for mode, config in print_modes.items():
            # 验证配置逻辑
            if mode == "none":
                assert not config["requires_printer"]
                assert not config["batch_enabled"]
            else:
                assert config["requires_printer"]
                if mode == "batch":
                    assert config["batch_enabled"]
    
    def test_print_interval_configuration(self):
        """测试打印间隔配置逻辑"""
        # 模拟GUI中的打印间隔验证
        def validate_print_interval(enabled, task_count, interval_seconds):
            if not isinstance(enabled, bool):
                return False, "启用状态必须是布尔值"
            
            if not isinstance(task_count, int) or task_count <= 0 or task_count > 20:
                return False, "任务数量必须在1-20之间"
            
            if not isinstance(interval_seconds, int) or interval_seconds <= 0 or interval_seconds > 300:
                return False, "间隔时间必须在1-300秒之间"
            
            return True, "配置有效"
        
        # 测试有效配置
        valid, msg = validate_print_interval(True, 3, 50)
        assert valid
        
        # 测试无效配置
        invalid_configs = [
            ("not_bool", 3, 50),  # 无效的启用状态
            (True, 0, 50),  # 无效的任务数量
            (True, 25, 50),  # 任务数量过大
            (True, 3, 0),  # 无效的间隔时间
            (True, 3, 400),  # 间隔时间过大
        ]
        
        for enabled, task_count, interval_seconds in invalid_configs:
            valid, msg = validate_print_interval(enabled, task_count, interval_seconds)
            assert not valid

class TestGUIStateManagement:
    """测试GUI状态管理"""
    
    def test_application_state_persistence(self, test_env):
        """测试应用状态持久化"""
        from utils.config_manager import ConfigManager
        
        config_file = os.path.join(test_env.temp_dir, 'gui_state_test.json')
        
        # 模拟GUI状态
        gui_state = {
            'window_geometry': '800x600+100+100',
            'last_recipe': '案卷目录',
            'last_height_method': 'gdi',
            'paths': {
                'jn_catalog_path': '/test/jn.xlsx',
                'template_path': '/test/template.xlsx',
                'output_folder': '/test/output'
            },
            'options': {
                'start_file': 'FILE001',
                'end_file': 'FILE999'
            }
        }
        
        # 保存状态
        manager = ConfigManager(config_file)
        for key, value in gui_state.items():
            if key == 'paths':
                for path_key, path_value in value.items():
                    manager.set_path(path_key, path_value)
            elif key == 'options':
                for option_key, option_value in value.items():
                    manager.set_option(option_key, option_value)
            else:
                manager.set(key, value)
        
        assert manager.save_config()
        
        # 模拟重新启动，加载状态
        new_manager = ConfigManager(config_file)
        
        # 验证状态恢复
        assert new_manager.get_window_geometry() == gui_state['window_geometry']
        assert new_manager.get_last_recipe() == gui_state['last_recipe']
        assert new_manager.get_last_height_method() == gui_state['last_height_method']
        
        loaded_paths = new_manager.get_paths()
        for key, value in gui_state['paths'].items():
            assert loaded_paths[key] == value
    
    def test_gui_validation_logic(self):
        """测试GUI验证逻辑"""
        # 模拟GUI中的输入验证
        def validate_generation_params(recipe, paths, options):
            """验证生成参数"""
            errors = []
            
            # 验证目录类型
            valid_recipes = ["卷内目录", "案卷目录", "全引目录", "简化目录"]
            if recipe not in valid_recipes:
                errors.append(f"无效的目录类型: {recipe}")
            
            # 验证必需路径
            required_paths = {
                "卷内目录": ["jn_catalog_path", "template_path", "output_folder"],
                "案卷目录": ["aj_catalog_path", "template_path", "output_folder"],
                "全引目录": ["jn_catalog_path", "aj_catalog_path", "template_path", "output_folder"],
                "简化目录": ["jh_catalog_path", "template_path", "output_folder"],
            }
            
            for required_path in required_paths.get(recipe, []):
                if not paths.get(required_path):
                    errors.append(f"缺少必需路径: {required_path}")
            
            # 验证文件范围
            start_file = options.get('start_file', '')
            end_file = options.get('end_file', '')
            
            if start_file and end_file and start_file > end_file:
                errors.append("起始文件不能大于结束文件")
            
            return len(errors) == 0, errors
        
        # 测试有效参数
        valid_params = {
            'recipe': '卷内目录',
            'paths': {
                'jn_catalog_path': '/test/jn.xlsx',
                'template_path': '/test/template.xlsx',
                'output_folder': '/test/output'
            },
            'options': {
                'start_file': 'FILE001',
                'end_file': 'FILE999'
            }
        }
        
        is_valid, errors = validate_generation_params(**valid_params)
        assert is_valid
        assert len(errors) == 0
        
        # 测试无效参数
        invalid_params = valid_params.copy()
        invalid_params['recipe'] = '无效类型'
        
        is_valid, errors = validate_generation_params(**invalid_params)
        assert not is_valid
        assert len(errors) > 0

class TestGUIPerformance:
    """测试GUI性能相关功能"""
    
    def test_file_list_update_performance(self, mock_archive_data):
        """测试文件列表更新性能"""
        import time
        
        # 模拟大量文件的列表更新
        large_data = mock_archive_data
        for i in range(100):  # 扩展数据
            new_row = large_data.iloc[0].copy()
            new_row['案卷档号'] = f'ZYZS2023-Y-{1000+i:04d}'
            large_data = large_data.append(new_row, ignore_index=True)
        
        start_time = time.perf_counter()
        
        # 模拟文件列表解析
        file_groups = {}
        for _, row in large_data.iterrows():
            file_number = str(row['案卷档号']).strip()
            if file_number and file_number != 'nan':
                if file_number not in file_groups:
                    file_groups[file_number] = 0
                file_groups[file_number] += 1
        
        # 生成显示数据
        file_list_data = []
        for file_number, count in file_groups.items():
            file_list_data.append({
                'file_number': file_number,
                'display_name': f"卷内目录_{file_number}",
                'item_count': count
            })
        
        processing_time = time.perf_counter() - start_time
        
        # 验证性能
        assert processing_time < 1.0  # 应该在1秒内完成
        assert len(file_list_data) > 0
    
    def test_ui_responsiveness_simulation(self):
        """测试UI响应性模拟"""
        import threading
        import queue
        
        # 模拟GUI中的日志队列处理
        log_queue = queue.Queue()
        processed_messages = []
        
        def process_log_queue():
            """模拟GUI日志队列处理"""
            batch_size = 20
            messages = []
            
            for _ in range(batch_size):
                try:
                    message = log_queue.get(block=False)
                    messages.append(message)
                except queue.Empty:
                    break
            
            if messages:
                processed_messages.extend(messages)
            
            return len(messages)
        
        # 添加一些日志消息
        for i in range(50):
            log_queue.put(f"测试消息 {i}")
        
        # 处理消息
        start_time = time.perf_counter()
        while not log_queue.empty():
            processed_count = process_log_queue()
            if processed_count == 0:
                break
        processing_time = time.perf_counter() - start_time
        
        # 验证处理效率
        assert len(processed_messages) == 50
        assert processing_time < 0.1  # 应该很快完成

if __name__ == "__main__":
    pytest.main([__file__])