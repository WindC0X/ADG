"""
Excel文件格式转换模块
提供安全的Excel文件格式转换功能
"""

import win32com.client as win32
import os
import logging
from typing import Optional
from pathlib import Path

# 导入文件验证器
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.file_validator import FileValidator, validate_excel_file


class ExcelConverter:
    """安全的Excel格式转换器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def xlsx2xls(self, file_path: str) -> Optional[str]:
        """
        安全地将xlsx文件转换为xls格式
        
        Args:
            file_path: 输入的xlsx文件路径
            
        Returns:
            str: 转换后的xls文件路径，转换失败返回None
            
        Raises:
            ValueError: 文件路径不安全或不存在
            RuntimeError: Excel操作失败
        """
        # 验证输入文件路径安全性
        if not validate_excel_file(file_path):
            raise ValueError(f"不安全或无效的文件路径: {file_path}")
        
        # 检查文件扩展名
        if not file_path.lower().endswith('.xlsx'):
            raise ValueError("输入文件必须是.xlsx格式")
        
        excel_app = None
        workbook = None
        
        try:
            # 生成安全的输出路径
            output_path = FileValidator.generate_safe_output_path(file_path, '.xls')
            
            self.logger.info(f"开始转换 {file_path} -> {output_path}")
            
            # 创建Excel应用程序实例
            excel_app = win32.gencache.EnsureDispatch("Excel.Application")
            excel_app.Visible = False  # 隐藏Excel窗口
            excel_app.DisplayAlerts = False  # 禁用警告对话框
            
            # 打开工作簿
            workbook = excel_app.Workbooks.Open(file_path)
            
            # 保存为xls格式 (FileFormat=56 表示Excel 97-2003格式)
            workbook.SaveAs(output_path, FileFormat=56)
            
            self.logger.info(f"转换成功: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"转换xlsx为xls时出错: {e}")
            raise RuntimeError(f"Excel转换失败: {e}")
            
        finally:
            # 确保资源正确释放
            self._cleanup_excel_resources(workbook, excel_app)
    
    def xls2xlsx(self, file_path: str) -> Optional[str]:
        """
        安全地将xls文件转换为xlsx格式
        
        Args:
            file_path: 输入的xls文件路径
            
        Returns:
            str: 转换后的xlsx文件路径，转换失败返回None
            
        Raises:
            ValueError: 文件路径不安全或不存在
            RuntimeError: Excel操作失败
        """
        # 验证输入文件路径安全性
        if not validate_excel_file(file_path):
            raise ValueError(f"不安全或无效的文件路径: {file_path}")
        
        # 检查文件扩展名
        if not file_path.lower().endswith('.xls'):
            raise ValueError("输入文件必须是.xls格式")
        
        excel_app = None
        workbook = None
        
        try:
            # 生成安全的输出路径
            output_path = FileValidator.generate_safe_output_path(file_path, '.xlsx')
            
            self.logger.info(f"开始转换 {file_path} -> {output_path}")
            
            # 创建Excel应用程序实例
            excel_app = win32.gencache.EnsureDispatch("Excel.Application")
            excel_app.Visible = False  # 隐藏Excel窗口
            excel_app.DisplayAlerts = False  # 禁用警告对话框
            
            # 打开工作簿
            workbook = excel_app.Workbooks.Open(file_path)
            
            # 保存为xlsx格式 (FileFormat=51 表示Excel 2007-2019格式)
            workbook.SaveAs(output_path, FileFormat=51)
            
            self.logger.info(f"转换成功: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"转换xls为xlsx时出错: {e}")
            raise RuntimeError(f"Excel转换失败: {e}")
            
        finally:
            # 确保资源正确释放
            self._cleanup_excel_resources(workbook, excel_app)
    
    def _cleanup_excel_resources(self, workbook, excel_app):
        """
        清理Excel COM资源
        
        Args:
            workbook: Excel工作簿对象
            excel_app: Excel应用程序对象
        """
        try:
            # 关闭工作簿
            if workbook is not None:
                workbook.Close(SaveChanges=False)
                self.logger.debug("工作簿已关闭")
                
        except Exception as e:
            self.logger.warning(f"关闭工作簿时出错: {e}")
        
        try:
            # 退出Excel应用程序
            if excel_app is not None:
                excel_app.Quit()
                self.logger.debug("Excel应用程序已退出")
                
        except Exception as e:
            self.logger.warning(f"退出Excel应用程序时出错: {e}")
        
        finally:
            # 释放COM对象引用
            try:
                if workbook is not None:
                    del workbook
                if excel_app is not None:
                    del excel_app
            except Exception as e:
                self.logger.warning(f"释放COM对象时出错: {e}")


# 便捷函数，保持向后兼容性
def xlsx2xls(file_path: str) -> Optional[str]:
    """将xlsx文件转换为xls格式的便捷函数"""
    converter = ExcelConverter()
    return converter.xlsx2xls(file_path)


def xls2xlsx(file_path: str) -> Optional[str]:
    """将xls文件转换为xlsx格式的便捷函数"""
    converter = ExcelConverter()
    return converter.xls2xlsx(file_path)


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 示例用法（仅用于测试）
    # 注意：实际使用时应该通过适当的输入验证获取文件路径
    test_file_path = r"path/to/your/excel/file.xlsx"
    
    if os.path.exists(test_file_path):
        try:
            converter = ExcelConverter()
            result = converter.xlsx2xls(test_file_path)
            if result:
                print(f"转换成功: {result}")
            else:
                print("转换失败")
        except Exception as e:
            print(f"转换过程中出错: {e}")
    else:
        print("测试文件不存在，跳过转换测试")
