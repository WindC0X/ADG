"""
文件安全验证模块
提供文件路径验证和安全检查功能
"""

import os
import logging
from pathlib import Path
from typing import List, Optional


class FileValidator:
    """文件安全验证器"""
    
    # 允许的Excel文件扩展名
    ALLOWED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
    
    # 最大文件大小限制（100MB）
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def validate_file_path(file_path: str, allowed_extensions: Optional[List[str]] = None) -> bool:
        """
        验证文件路径的安全性
        
        Args:
            file_path: 要验证的文件路径
            allowed_extensions: 允许的文件扩展名列表
            
        Returns:
            bool: 路径是否安全
        """
        if not file_path or not isinstance(file_path, str):
            return False
            
        try:
            # 使用Path进行安全的路径解析
            path = Path(file_path).resolve()
            
            # 检查路径是否包含危险字符
            if '..' in str(path) or path.name.startswith('.'):
                return False
            
            # 检查文件是否存在
            if not path.exists():
                return False
                
            # 检查是否是文件（不是目录）
            if not path.is_file():
                return False
            
            # 检查文件扩展名
            if allowed_extensions:
                if path.suffix.lower() not in [ext.lower() for ext in allowed_extensions]:
                    return False
            
            # 检查文件大小
            if path.stat().st_size > FileValidator.MAX_FILE_SIZE:
                return False
                
            # 检查文件读取权限
            if not os.access(path, os.R_OK):
                return False
                
            return True
            
        except (OSError, ValueError, PermissionError) as e:
            logging.warning(f"路径验证失败: {file_path}, 错误: {e}")
            return False
    
    @staticmethod
    def validate_directory_path(dir_path: str) -> bool:
        """
        验证目录路径的安全性
        
        Args:
            dir_path: 要验证的目录路径
            
        Returns:
            bool: 目录路径是否安全
        """
        if not dir_path or not isinstance(dir_path, str):
            return False
            
        try:
            path = Path(dir_path).resolve()
            
            # 检查路径是否包含危险字符
            if '..' in str(path):
                return False
            
            # 检查目录是否存在
            if not path.exists():
                return False
                
            # 检查是否是目录
            if not path.is_dir():
                return False
            
            # 检查目录写入权限
            if not os.access(path, os.W_OK):
                return False
                
            return True
            
        except (OSError, ValueError, PermissionError) as e:
            logging.warning(f"目录验证失败: {dir_path}, 错误: {e}")
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，移除危险字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的安全文件名
        """
        if not filename:
            return "untitled"
            
        # 移除或替换危险字符
        dangerous_chars = '<>:"/\\|?*'
        safe_filename = filename
        
        for char in dangerous_chars:
            safe_filename = safe_filename.replace(char, '_')
        
        # 移除前后空格和点号
        safe_filename = safe_filename.strip('. ')
        
        # 确保文件名不为空
        if not safe_filename:
            safe_filename = "untitled"
            
        return safe_filename
    
    @staticmethod
    def generate_safe_output_path(input_path: str, new_extension: str) -> str:
        """
        生成安全的输出文件路径
        
        Args:
            input_path: 输入文件路径
            new_extension: 新的文件扩展名（包含点号，如'.xlsx'）
            
        Returns:
            str: 安全的输出文件路径
        """
        try:
            input_path_obj = Path(input_path)
            
            # 获取安全的文件名（不含扩展名）
            safe_stem = FileValidator.sanitize_filename(input_path_obj.stem)
            
            # 构建新的文件路径
            output_path = input_path_obj.parent / f"{safe_stem}{new_extension}"
            
            return str(output_path)
            
        except Exception as e:
            logging.error(f"生成输出路径失败: {input_path}, 错误: {e}")
            raise ValueError(f"无法生成安全的输出路径: {e}")


# 便捷函数
def validate_excel_file(file_path: str) -> bool:
    """验证Excel文件路径"""
    return FileValidator.validate_file_path(
        file_path, 
        list(FileValidator.ALLOWED_EXCEL_EXTENSIONS)
    )


def validate_output_directory(dir_path: str) -> bool:
    """验证输出目录路径"""
    return FileValidator.validate_directory_path(dir_path)