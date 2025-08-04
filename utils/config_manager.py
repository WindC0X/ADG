"""
配置管理器模块
提供应用程序配置的持久化存储和加载功能
"""

import json
import os
from typing import Dict, Any, Optional


class ConfigManager:
    """应用程序配置管理器"""
    
    def __init__(self, config_file: str = "app_config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件名称，默认保存在程序目录
        """
        self.config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_file)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 验证配置文件结构
                if self._validate_config_structure(config_data):
                    return config_data
                else:
                    print(f"配置文件结构无效，使用默认配置: {self.config_file}")
                    return self._get_default_config()
                    
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                print(f"加载配置文件失败: {e}")
        
        # 返回默认配置
        return self._get_default_config()
    
    def _validate_config_structure(self, config: Dict[str, Any]) -> bool:
        """
        验证配置文件结构的完整性和安全性
        
        Args:
            config: 要验证的配置字典
            
        Returns:
            bool: 配置是否有效
        """
        if not isinstance(config, dict):
            return False
        
        # 定义必需的配置字段和类型
        required_schema = {
            "paths": dict,
            "last_recipe": str,
            "last_height_method": str,
            "window_geometry": str,
            "options": dict
        }
        
        # 检查必需字段
        for key, expected_type in required_schema.items():
            if key not in config:
                print(f"缺少必需的配置字段: {key}")
                return False
            
            if not isinstance(config[key], expected_type):
                print(f"配置字段类型错误: {key}, 期望 {expected_type.__name__}, 实际 {type(config[key]).__name__}")
                return False
        
        # 验证路径配置
        if not self._validate_paths_config(config["paths"]):
            return False
        
        # 验证recipe值
        valid_recipes = ["卷内目录", "案卷目录", "全引目录", "简化目录"]
        if config["last_recipe"] not in valid_recipes:
            print(f"无效的last_recipe值: {config['last_recipe']}")
            return False
        
        # 验证行高方案
        valid_methods = ["xlwings", "gdi", "pillow"]
        if config["last_height_method"] not in valid_methods:
            print(f"无效的last_height_method值: {config['last_height_method']}")
            return False
        
        # 验证窗口几何字符串格式
        if not self._validate_geometry_string(config["window_geometry"]):
            return False
        
        return True
    
    def _validate_paths_config(self, paths: Dict[str, str]) -> bool:
        """验证路径配置的安全性"""
        if not isinstance(paths, dict):
            return False
        
        expected_path_keys = {
            "jn_catalog_path", "aj_catalog_path", "jh_catalog_path", 
            "template_path", "output_folder"
        }
        
        # 检查是否包含预期的路径键
        for key in expected_path_keys:
            if key not in paths:
                print(f"缺少路径配置: {key}")
                return False
            
            path_value = paths[key]
            if not isinstance(path_value, str):
                print(f"路径值类型错误: {key}")
                return False
            
            # 如果路径不为空，验证其安全性
            if path_value and not self._is_safe_path(path_value):
                print(f"不安全的路径配置: {key} = {path_value}")
                return False
        
        return True
    
    def _is_safe_path(self, path: str) -> bool:
        """检查路径是否安全"""
        if not path:
            return True  # 空路径是安全的
        
        try:
            # 检查是否包含危险字符或模式
            dangerous_patterns = ['../', '..\\', '<', '>', '|', '*', '?']
            for pattern in dangerous_patterns:
                if pattern in path:
                    return False
            
            # 检查路径长度
            if len(path) > 260:  # Windows路径长度限制
                return False
            
            # 尝试解析路径（不实际访问文件系统）
            from pathlib import Path
            Path(path)  # 这会验证路径格式但不访问文件
            
            return True
            
        except (ValueError, OSError):
            return False
    
    def _validate_geometry_string(self, geometry: str) -> bool:
        """验证窗口几何字符串格式"""
        if not isinstance(geometry, str):
            return False
        
        # 基本格式检查：宽x高 或 宽x高+x+y
        import re
        pattern = r'^\d+x\d+(\+\d+\+\d+)?$'
        return bool(re.match(pattern, geometry))
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "paths": {
                "jn_catalog_path": "",
                "aj_catalog_path": "",
                "jh_catalog_path": "",
                "template_path": "",
                "output_folder": ""
            },
            "last_recipe": "卷内目录",
            "last_height_method": "xlwings",
            "window_geometry": "850x650",
            "options": {
                "start_file": "",
                "end_file": ""
            }
        }
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except OSError as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        keys = key.split('.')
        config = self.config
        
        # 创建嵌套字典结构
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_paths(self) -> Dict[str, str]:
        """获取所有路径配置"""
        return self.get("paths", {})
    
    def set_path(self, path_key: str, path_value: str) -> None:
        """设置路径配置"""
        self.set(f"paths.{path_key}", path_value)
    
    def get_last_recipe(self) -> str:
        """获取上次选择的目录类型"""
        return self.get("last_recipe", "卷内目录")
    
    def set_last_recipe(self, recipe: str) -> None:
        """设置上次选择的目录类型"""
        self.set("last_recipe", recipe)
    
    def get_last_height_method(self) -> str:
        """获取上次选择的行高计算方案"""
        return self.get("last_height_method", "xlwings")
    
    def set_last_height_method(self, method: str) -> None:
        """设置上次选择的行高计算方案"""
        self.set("last_height_method", method)
    
    def get_window_geometry(self) -> str:
        """获取窗口几何配置"""
        return self.get("window_geometry", "850x650")
    
    def set_window_geometry(self, geometry: str) -> None:
        """设置窗口几何配置"""
        self.set("window_geometry", geometry)
    
    def get_options(self) -> Dict[str, str]:
        """获取可选参数配置"""
        return self.get("options", {})
    
    def set_option(self, option_key: str, option_value: str) -> None:
        """设置可选参数"""
        self.set(f"options.{option_key}", option_value)


# 全局配置管理器实例
_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager