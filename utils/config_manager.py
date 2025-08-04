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
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"加载配置文件失败: {e}")
        
        # 返回默认配置
        return self._get_default_config()
    
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