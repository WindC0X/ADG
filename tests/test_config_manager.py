"""
配置管理器模块单元测试
测试utils/config_manager.py的配置持久化和验证功能
"""

import pytest
import sys
import os
import json
import tempfile
from unittest.mock import patch, mock_open

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import benchmark

class TestConfigManager:
    """测试配置管理器基本功能"""
    
    def test_default_config_structure(self, test_env):
        """测试默认配置结构"""
        from utils.config_manager import ConfigManager
        
        # 在临时目录创建配置管理器
        config_file = os.path.join(test_env.temp_dir, 'test_config.json')
        manager = ConfigManager(config_file)
        
        # 验证默认配置结构
        config = manager.config
        assert 'paths' in config
        assert 'last_recipe' in config
        assert 'last_height_method' in config
        assert 'window_geometry' in config
        assert 'options' in config
        assert 'print_interval' in config
        
        # 验证路径配置
        paths = config['paths']
        expected_path_keys = {
            'jn_catalog_path', 'aj_catalog_path', 'jh_catalog_path',
            'template_path', 'output_folder'
        }
        assert set(paths.keys()) == expected_path_keys
        
        # 验证默认值
        assert config['last_recipe'] == '卷内目录'
        assert config['last_height_method'] == 'xlwings'
        assert '650' in config['window_geometry']  # 包含默认高度
    
    def test_save_and_load_config(self, test_env):
        """测试配置保存和加载"""
        from utils.config_manager import ConfigManager
        
        config_file = os.path.join(test_env.temp_dir, 'save_load_test.json')
        
        # 创建配置管理器并修改配置
        manager1 = ConfigManager(config_file)
        manager1.set_last_recipe('案卷目录')
        manager1.set_path('template_path', '/test/template.xlsx')
        manager1.set_option('start_file', 'TEST001')
        
        # 保存配置
        assert manager1.save_config() == True
        
        # 创建新的配置管理器实例
        manager2 = ConfigManager(config_file)
        
        # 验证配置被正确加载
        assert manager2.get_last_recipe() == '案卷目录'
        assert manager2.get('paths.template_path') == '/test/template.xlsx'
        assert manager2.get_options()['start_file'] == 'TEST001'
    
    def test_config_validation(self, test_env):
        """测试配置验证功能"""
        from utils.config_manager import ConfigManager
        
        config_file = os.path.join(test_env.temp_dir, 'validation_test.json')
        
        # 创建无效的配置文件
        invalid_config = {
            'paths': 'invalid_type',  # 应该是dict
            'last_recipe': 'invalid_recipe',  # 无效的recipe
            'last_height_method': 'invalid_method',  # 无效的方法
            'window_geometry': 'invalid_geometry',  # 无效的几何格式
            'options': {},
            'print_interval': {}
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(invalid_config, f)
        
        # 创建配置管理器，应该使用默认配置
        manager = ConfigManager(config_file)
        
        # 验证使用了默认配置而不是无效配置
        assert isinstance(manager.config['paths'], dict)
        assert manager.get_last_recipe() == '卷内目录'
        assert manager.get_last_height_method() == 'xlwings'
    
    def test_path_security_validation(self, test_env):
        """测试路径安全验证"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'security_test.json'))
        
        # 测试危险路径
        dangerous_paths = [
            '../../../etc/passwd',  # 路径遍历
            'C:\\Windows\\System32\\<script>',  # 包含危险字符
            'very_long_path_' + 'x' * 300,  # 过长路径
            'path|with|pipes',  # 包含管道符
            'path*with*wildcards',  # 包含通配符
        ]
        
        for dangerous_path in dangerous_paths:
            # 验证不安全路径被拒绝
            result = manager._is_safe_path(dangerous_path)
            assert result == False, f"路径 '{dangerous_path}' 应该被标记为不安全"
        
        # 测试安全路径
        safe_paths = [
            '',  # 空路径
            'C:\\Users\\Test\\Documents\\file.xlsx',
            '/home/user/documents/template.xlsx',
            'relative/path/file.xlsx',
        ]
        
        for safe_path in safe_paths:
            result = manager._is_safe_path(safe_path)
            assert result == True, f"路径 '{safe_path}' 应该被标记为安全"

class TestConfigManagerGettersSetters:
    """测试配置管理器的getter和setter方法"""
    
    def test_path_operations(self, test_env):
        """测试路径操作"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'path_test.json'))
        
        # 测试设置路径
        test_paths = {
            'jn_catalog_path': '/test/jn_catalog.xlsx',
            'aj_catalog_path': '/test/aj_catalog.xlsx',
            'template_path': '/test/template.xlsx',
            'output_folder': '/test/output'
        }
        
        for key, value in test_paths.items():
            manager.set_path(key, value)
        
        # 测试获取路径
        paths = manager.get_paths()
        for key, value in test_paths.items():
            assert paths[key] == value
    
    def test_recipe_operations(self, test_env):
        """测试目录类型操作"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'recipe_test.json'))
        
        # 测试设置目录类型
        recipes = ['卷内目录', '案卷目录', '全引目录', '简化目录']
        
        for recipe in recipes:
            manager.set_last_recipe(recipe)
            assert manager.get_last_recipe() == recipe
    
    def test_height_method_operations(self, test_env):
        """测试行高方案操作"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'method_test.json'))
        
        # 测试设置行高方案
        methods = ['xlwings', 'gdi', 'pillow']
        
        for method in methods:
            manager.set_last_height_method(method)
            assert manager.get_last_height_method() == method
    
    def test_window_geometry_operations(self, test_env):
        """测试窗口几何操作"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'geometry_test.json'))
        
        # 测试设置窗口几何
        geometries = ['800x600', '1024x768+100+100', '1200x900+50+50']
        
        for geometry in geometries:
            manager.set_window_geometry(geometry)
            assert manager.get_window_geometry() == geometry
    
    def test_options_operations(self, test_env):
        """测试可选参数操作"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'options_test.json'))
        
        # 测试设置可选参数
        test_options = {
            'start_file': 'FILE001',
            'end_file': 'FILE999'
        }
        
        for key, value in test_options.items():
            manager.set_option(key, value)
        
        # 测试获取可选参数
        options = manager.get_options()
        for key, value in test_options.items():
            assert options[key] == value
    
    def test_print_interval_operations(self, test_env):
        """测试打印间隔配置操作"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'interval_test.json'))
        
        # 测试设置打印间隔配置
        interval_config = {
            'enabled': True,
            'task_count': 5,
            'interval_seconds': 60
        }
        
        manager.set_print_interval_config(interval_config)
        loaded_config = manager.get_print_interval_config()
        
        assert loaded_config['enabled'] == True
        assert loaded_config['task_count'] == 5
        assert loaded_config['interval_seconds'] == 60
        
        # 测试单独设置
        manager.set_print_interval_enabled(False)
        assert manager.get_print_interval_enabled() == False
        
        manager.set_print_interval_task_count(10)
        assert manager.get_print_interval_task_count() == 10
        
        manager.set_print_interval_seconds(120)
        assert manager.get_print_interval_seconds() == 120

class TestConfigManagerValidation:
    """测试配置管理器验证功能"""
    
    def test_geometry_string_validation(self, test_env):
        """测试几何字符串验证"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'geo_validation_test.json'))
        
        # 有效的几何字符串
        valid_geometries = [
            '800x600',
            '1024x768+100+100',
            '1200x900+0+0',
            '640x480+50+25'
        ]
        
        for geometry in valid_geometries:
            assert manager._validate_geometry_string(geometry) == True
        
        # 无效的几何字符串
        invalid_geometries = [
            'invalid',
            '800x',
            'x600',
            '800x600+',
            '800x600+100',
            '800x600+100+',
            'abc',
            '',
            123,  # 非字符串类型
            None
        ]
        
        for geometry in invalid_geometries:
            assert manager._validate_geometry_string(geometry) == False
    
    def test_print_interval_validation(self, test_env):
        """测试打印间隔配置验证"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'interval_validation_test.json'))
        
        # 有效的打印间隔配置
        valid_configs = [
            {'enabled': True, 'task_count': 1, 'interval_seconds': 1},
            {'enabled': False, 'task_count': 50, 'interval_seconds': 300},
            {'enabled': True, 'task_count': 100, 'interval_seconds': 3600}
        ]
        
        for config in valid_configs:
            assert manager._validate_print_interval_config(config) == True
        
        # 无效的打印间隔配置
        invalid_configs = [
            'not_a_dict',  # 非字典类型
            {},  # 缺少字段
            {'enabled': True},  # 缺少字段
            {'enabled': 'not_bool', 'task_count': 5, 'interval_seconds': 30},  # 类型错误
            {'enabled': True, 'task_count': 0, 'interval_seconds': 30},  # 数值范围错误
            {'enabled': True, 'task_count': 101, 'interval_seconds': 30},  # 数值范围错误
            {'enabled': True, 'task_count': 5, 'interval_seconds': 0},  # 数值范围错误
            {'enabled': True, 'task_count': 5, 'interval_seconds': 3601},  # 数值范围错误
        ]
        
        for config in invalid_configs:
            assert manager._validate_print_interval_config(config) == False

class TestConfigManagerErrorHandling:
    """测试配置管理器错误处理"""
    
    def test_corrupted_config_file(self, test_env):
        """测试损坏的配置文件处理"""
        from utils.config_manager import ConfigManager
        
        config_file = os.path.join(test_env.temp_dir, 'corrupted.json')
        
        # 创建损坏的JSON文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write('{ invalid json content ,,, }')
        
        # 创建配置管理器，应该使用默认配置
        manager = ConfigManager(config_file)
        
        # 验证使用了默认配置
        assert manager.get_last_recipe() == '卷内目录'
        assert manager.get_last_height_method() == 'xlwings'
    
    def test_permission_error_handling(self, test_env):
        """测试权限错误处理"""
        from utils.config_manager import ConfigManager
        
        config_file = os.path.join(test_env.temp_dir, 'permission_test.json')
        manager = ConfigManager(config_file)
        
        # 模拟权限错误
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            result = manager.save_config()
            assert result == False
    
    def test_config_performance(self, test_env):
        """测试配置操作性能"""
        import time  # 添加time导入
        from utils.config_manager import ConfigManager
        
        config_file = os.path.join(test_env.temp_dir, 'performance_test.json')
        manager = ConfigManager(config_file)
        
        start_time = time.perf_counter()
        
        # 批量设置操作
        for i in range(100):
            manager.set_path('template_path', f'/test/template_{i}.xlsx')
            manager.set_option('start_file', f'FILE_{i:03d}')
            manager.set_last_recipe('案卷目录')
        
        # 保存配置
        result = manager.save_config()
        assert result == True
        
        # 批量获取操作
        for i in range(100):
            template_path = manager.get('paths.template_path')
            start_file = manager.get('options.start_file')
            recipe = manager.get_last_recipe()
            
            assert template_path is not None
            assert start_file is not None
            assert recipe is not None
        
        total_time = time.perf_counter() - start_time
        assert total_time < 5.0  # 应该在5秒内完成

class TestConfigManagerSingleton:
    """测试配置管理器单例模式"""
    
    def test_singleton_pattern(self):
        """测试全局配置管理器单例"""
        from utils.config_manager import get_config_manager
        
        # 获取两个实例
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        # 应该是同一个实例
        assert manager1 is manager2
    
    def test_singleton_state_persistence(self):
        """测试单例状态持久性"""
        from utils.config_manager import get_config_manager
        
        # 第一次获取并设置值
        manager1 = get_config_manager()
        manager1.set_last_recipe('测试目录')
        
        # 第二次获取应该保持状态
        manager2 = get_config_manager()
        assert manager2.get_last_recipe() == '测试目录'

class TestConfigManagerNestingAndDotNotation:
    """测试配置管理器嵌套和点记法"""
    
    def test_nested_config_access(self, test_env):
        """测试嵌套配置访问"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'nested_test.json'))
        
        # 测试设置嵌套值
        manager.set('deep.nested.value', 'test_value')
        manager.set('another.path.setting', 42)
        
        # 测试获取嵌套值
        assert manager.get('deep.nested.value') == 'test_value'
        assert manager.get('another.path.setting') == 42
        
        # 测试获取不存在的值
        assert manager.get('nonexistent.path', 'default') == 'default'
        assert manager.get('nonexistent.path') is None
    
    def test_config_structure_preservation(self, test_env):
        """测试配置结构保持"""
        from utils.config_manager import ConfigManager
        
        manager = ConfigManager(os.path.join(test_env.temp_dir, 'structure_test.json'))
        
        # 设置复杂的嵌套结构
        manager.set('section1.subsection.item1', 'value1')
        manager.set('section1.subsection.item2', 'value2')
        manager.set('section2.item', 'value3')
        
        # 保存并重新加载
        assert manager.save_config() == True
        
        manager2 = ConfigManager(os.path.join(test_env.temp_dir, 'structure_test.json'))
        
        # 验证结构被保持
        assert manager2.get('section1.subsection.item1') == 'value1'
        assert manager2.get('section1.subsection.item2') == 'value2'
        assert manager2.get('section2.item') == 'value3'

if __name__ == "__main__":
    pytest.main([__file__])