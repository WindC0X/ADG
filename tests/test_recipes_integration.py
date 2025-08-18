"""
业务配方模块集成测试
测试utils/recipes.py中各种目录生成配方的完整流程
"""

import pytest
import sys
import os
import pandas as pd
import threading
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import (
    benchmark,
    create_mock_archive_data,
    create_mock_template,
    MockHeightCalculator,
    skip_without_excel
)

class TestRecipeIntegration:
    """测试业务配方集成"""
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template') 
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_create_jn_or_jh_index_basic(self, mock_app, mock_cleanup, mock_get_subset,
                                        mock_generate, mock_prepare_template, mock_load_data,
                                        test_env, mock_archive_data):
        """测试卷内/简化目录生成基本流程"""
        from utils.recipes import create_jn_or_jh_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = mock_archive_data['案卷档号'].unique()
        mock_generate.return_value = 2  # 模拟生成2页
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试
        create_jn_or_jh_index(
            catalog_path='test_catalog.xlsx',
            template_path='test_template.xlsx', 
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录',
            start_file='',
            end_file='',
            direct_print=False,
            printer_name=None,
            print_copies=1,
            cancel_flag=None
        )
        
        # 验证调用
        mock_load_data.assert_called_once()
        mock_prepare_template.assert_called_once()
        mock_get_subset.assert_called_once()
        assert mock_generate.call_count == len(mock_archive_data['案卷档号'].unique())
        mock_cleanup.assert_called_once()
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_create_aj_index_basic(self, mock_app, mock_cleanup, mock_get_subset,
                                  mock_generate, mock_prepare_template, mock_load_data,
                                  test_env, mock_archive_data):
        """测试案卷目录生成基本流程"""
        from utils.recipes import create_aj_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = mock_archive_data['案卷档号'].unique()
        mock_generate.return_value = 1  # 模拟生成1页
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试
        create_aj_index(
            catalog_path='test_catalog.xlsx',
            template_path='test_template.xlsx',
            output_folder=test_env.temp_dir,
            start_file='',
            end_file='',
            direct_print=False,
            printer_name=None,
            print_copies=1,
            cancel_flag=None
        )
        
        # 验证调用
        mock_load_data.assert_called_once()
        mock_prepare_template.assert_called_once()
        mock_get_subset.assert_called_once()
        assert mock_generate.call_count == len(mock_archive_data['案卷档号'].unique())
        mock_cleanup.assert_called_once()
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_create_qy_full_index_basic(self, mock_app, mock_cleanup, mock_get_subset,
                                       mock_generate, mock_prepare_template, mock_load_data,
                                       test_env, mock_archive_data):
        """测试全引目录生成基本流程"""
        from utils.recipes import create_qy_full_index
        
        # 设置模拟返回值
        mock_load_data.side_effect = [mock_archive_data, mock_archive_data]  # jn_data, aj_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = mock_archive_data['案卷档号'].unique()
        mock_generate.return_value = 3  # 模拟生成3页
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试
        create_qy_full_index(
            jn_catalog_path='test_jn_catalog.xlsx',
            aj_catalog_path='test_aj_catalog.xlsx',
            template_path='test_template.xlsx',
            output_folder=test_env.temp_dir,
            start_file='',
            end_file='',
            direct_print=False,
            printer_name=None,
            print_copies=1,
            cancel_flag=None
        )
        
        # 验证调用
        assert mock_load_data.call_count == 2  # 加载两个数据文件
        mock_prepare_template.assert_called_once()
        mock_get_subset.assert_called_once()
        assert mock_generate.call_count == len(mock_archive_data['案卷档号'].unique())
        mock_cleanup.assert_called_once()

class TestRecipeErrorHandling:
    """测试配方错误处理"""
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.xw.App')
    def test_missing_data_file_handling(self, mock_app, mock_prepare_template, mock_load_data):
        """测试数据文件缺失处理"""
        from utils.recipes import create_jn_or_jh_index
        
        # 模拟数据加载失败
        mock_load_data.return_value = None
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        
        # 执行测试，应该正常退出而不抛异常
        create_jn_or_jh_index(
            catalog_path='nonexistent.xlsx',
            template_path='template.xlsx',
            output_folder='/tmp',
            recipe_name='卷内目录'
        )
        
        # 验证只加载了数据，没有进一步处理
        mock_load_data.assert_called_once()
        # 由于数据加载失败，不应该尝试打开xlwings
        mock_app.assert_not_called()
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.xw.App')
    def test_missing_template_handling(self, mock_app, mock_prepare_template, mock_load_data,
                                      mock_archive_data):
        """测试模板文件缺失处理"""
        from utils.recipes import create_jn_or_jh_index
        
        # 模拟模板加载失败
        mock_load_data.return_value = mock_archive_data
        mock_prepare_template.return_value = None
        
        # 执行测试，应该正常退出而不抛异常
        create_jn_or_jh_index(
            catalog_path='catalog.xlsx',
            template_path='nonexistent_template.xlsx',
            output_folder='/tmp',
            recipe_name='卷内目录'
        )
        
        # 验证加载了数据和模板，但没有进一步处理
        mock_load_data.assert_called_once()
        mock_prepare_template.assert_called_once()
        mock_app.assert_not_called()
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.xw.App')
    def test_cancel_flag_handling(self, mock_app, mock_get_subset, mock_generate,
                                 mock_prepare_template, mock_load_data,
                                 test_env, mock_archive_data):
        """测试取消标志处理"""
        from utils.recipes import create_jn_or_jh_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = mock_archive_data['案卷档号'].unique()
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        
        # 创建取消标志并立即设置
        cancel_flag = threading.Event()
        cancel_flag.set()
        
        # 执行测试
        create_jn_or_jh_index(
            catalog_path='catalog.xlsx',
            template_path='template.xlsx',
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录',
            cancel_flag=cancel_flag
        )
        
        # 验证提前退出，没有调用生成函数
        mock_generate.assert_not_called()

class TestRecipePerformance:
    """测试配方性能"""
    
    @benchmark
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_recipe_performance_benchmark(self, mock_app, mock_cleanup, mock_get_subset,
                                         mock_generate, mock_prepare_template, mock_load_data,
                                         test_env):
        """配方性能基准测试"""
        from utils.recipes import create_jn_or_jh_index
        
        # 创建较大的测试数据集
        large_data = create_mock_archive_data(100)  # 100条记录
        
        # 设置模拟返回值
        mock_load_data.return_value = large_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = large_data['案卷档号'].unique()
        mock_generate.return_value = 1  # 快速返回
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行性能测试
        create_jn_or_jh_index(
            catalog_path='large_catalog.xlsx',
            template_path='template.xlsx',
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录'
        )
        
        # 验证处理了所有档案
        expected_calls = len(large_data['案卷档号'].unique())
        assert mock_generate.call_count == expected_calls
        
        return expected_calls

class TestRecipeFileHandling:
    """测试配方文件处理"""
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_selected_file_numbers_handling(self, mock_app, mock_cleanup, mock_get_subset,
                                           mock_generate, mock_prepare_template, mock_load_data,
                                           test_env, mock_archive_data):
        """测试选择性文件号处理"""
        from utils.recipes import create_jn_or_jh_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = ['ZYZS2023-Y-0001', 'ZYZS2023-Y-0003']  # 选择性文件
        mock_generate.return_value = 1
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试（传递选择的文件号）
        create_jn_or_jh_index(
            catalog_path='catalog.xlsx',
            template_path='template.xlsx',
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录',
            selected_file_numbers=['ZYZS2023-Y-0001', 'ZYZS2023-Y-0003']
        )
        
        # 验证只处理了选择的文件
        assert mock_generate.call_count == 2
        
        # 验证get_subset被正确调用
        mock_get_subset.assert_called_once()
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_file_range_filtering(self, mock_app, mock_cleanup, mock_get_subset,
                                 mock_generate, mock_prepare_template, mock_load_data,
                                 test_env, mock_archive_data):
        """测试文件范围过滤"""
        from utils.recipes import create_jn_or_jh_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        
        # 模拟get_subset返回过滤后的结果
        filtered_files = ['ZYZS2023-Y-0002', 'ZYZS2023-Y-0003', 'ZYZS2023-Y-0004']
        mock_get_subset.return_value = filtered_files
        mock_generate.return_value = 1
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试（指定起始和结束文件）
        create_jn_or_jh_index(
            catalog_path='catalog.xlsx',
            template_path='template.xlsx',
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录',
            start_file='ZYZS2023-Y-0002',
            end_file='ZYZS2023-Y-0004'
        )
        
        # 验证get_subset被正确调用，传入了范围参数
        mock_get_subset.assert_called_once()
        args, kwargs = mock_get_subset.call_args
        assert 'ZYZS2023-Y-0002' in args or 'ZYZS2023-Y-0002' in kwargs.values()
        assert 'ZYZS2023-Y-0004' in args or 'ZYZS2023-Y-0004' in kwargs.values()
        
        # 验证处理了过滤后的文件数量
        assert mock_generate.call_count == len(filtered_files)

class TestRecipePrintingIntegration:
    """测试配方打印集成"""
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_direct_print_mode(self, mock_app, mock_cleanup, mock_get_subset,
                              mock_generate, mock_prepare_template, mock_load_data,
                              test_env, mock_archive_data):
        """测试直接打印模式"""
        from utils.recipes import create_jn_or_jh_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = mock_archive_data['案卷档号'].unique()[:2]  # 只处理前2个
        mock_generate.return_value = 1
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试（启用直接打印）
        create_jn_or_jh_index(
            catalog_path='catalog.xlsx',
            template_path='template.xlsx',
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录',
            direct_print=True,
            printer_name='Test Printer',
            print_copies=2
        )
        
        # 验证generate函数被调用时传递了打印参数
        assert mock_generate.call_count >= 1
        
        # 检查最后一次调用的参数
        last_call_kwargs = mock_generate.call_args_list[-1][1]
        assert last_call_kwargs.get('direct_print') == True
        assert last_call_kwargs.get('printer_name') == 'Test Printer'
        assert last_call_kwargs.get('print_copies') == 2

class TestRecipeColumnMapping:
    """测试配方列映射"""
    
    @patch('utils.recipes.load_data')
    @patch('utils.recipes.prepare_template')
    @patch('utils.recipes.generate_one_archive_directory')
    @patch('utils.recipes.get_subset')
    @patch('utils.recipes.cleanup_stream')
    @patch('utils.recipes.xw.App')
    def test_jn_column_mapping(self, mock_app, mock_cleanup, mock_get_subset,
                              mock_generate, mock_prepare_template, mock_load_data,
                              test_env, mock_archive_data):
        """测试卷内目录列映射"""
        from utils.recipes import create_jn_or_jh_index
        
        # 设置模拟返回值
        mock_load_data.return_value = mock_archive_data
        mock_template_stream = BytesIO(create_mock_template())
        mock_prepare_template.return_value = mock_template_stream
        mock_get_subset.return_value = mock_archive_data['案卷档号'].unique()[:1]
        mock_generate.return_value = 1
        
        # 设置xlwings模拟
        mock_app_instance = Mock()
        mock_wb = Mock()
        mock_sheet = Mock()
        mock_range = Mock()
        
        mock_app.return_value = mock_app_instance
        mock_app_instance.books.open.return_value = mock_wb
        mock_wb.sheets = [mock_sheet]
        mock_sheet.range.return_value = mock_range
        mock_wb.close = Mock()
        mock_app_instance.quit = Mock()
        
        # 执行测试
        create_jn_or_jh_index(
            catalog_path='catalog.xlsx',
            template_path='template.xlsx',
            output_folder=test_env.temp_dir,
            recipe_name='卷内目录'
        )
        
        # 验证generate函数被调用时传递了正确的列映射
        assert mock_generate.call_count >= 1
        
        # 检查列映射参数
        call_kwargs = mock_generate.call_args_list[0][1]
        column_mapping = call_kwargs.get('column_mapping', {})
        
        # 卷内目录应该有序号、文件名、页数、备注等列
        assert 1 in column_mapping  # 序号列
        assert 2 in column_mapping  # 文件名列
        # 可以根据实际的列映射定义添加更多断言

if __name__ == "__main__":
    pytest.main([__file__])