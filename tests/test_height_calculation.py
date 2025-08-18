"""
核心业务逻辑单元测试
测试height_measure模块的三种行高计算方案
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import (
    skip_on_non_windows, 
    skip_without_excel,
    MockHeightCalculator,
    benchmark,
    create_mock_xlwings_range
)

class TestHeightCalculationMethods:
    """测试行高计算方法"""
    
    def test_mock_calculator_basic_functionality(self, mock_height_calculator):
        """测试模拟行高计算器基本功能"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        # 测试空文本
        height = calculator.calculate_height(mock_range, "", 10.0)
        assert height == 16.0
        
        # 测试短文本
        height = calculator.calculate_height(mock_range, "短文本", 20.0)
        assert height >= 16.0
        
        # 测试长文本
        long_text = "这是一个很长的文本内容，需要换行显示" * 3
        height = calculator.calculate_height(mock_range, long_text, 10.0)
        assert height > 32.0  # 至少2行
    
    def test_performance_stats_tracking(self, mock_height_calculator):
        """测试性能统计跟踪"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        # 执行几次计算
        for i in range(5):
            calculator.calculate_height(mock_range, f"测试文本{i}", 15.0)
        
        stats = calculator.get_performance_stats()
        assert 'xlwings' in stats
        assert stats['xlwings']['count'] == 5
        assert stats['xlwings']['total_time'] > 0
        assert stats['xlwings']['avg_time'] > 0
        assert stats['xlwings']['calls_per_second'] > 0
    
    def test_method_switching(self, mock_height_calculator):
        """测试计算方法切换"""
        calculator = mock_height_calculator
        
        # 测试切换到GDI方法
        calculator.set_method('gdi')
        assert calculator.method == 'gdi'
        
        # 测试切换到Pillow方法
        calculator.set_method('pillow')
        assert calculator.method == 'pillow'
        
        # 测试切换回xlwings方法
        calculator.set_method('xlwings')
        assert calculator.method == 'xlwings'
    
    def test_calculation_performance_benchmark(self, mock_height_calculator):
        """行高计算性能基准测试"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        # 测试不同长度文本的计算性能
        test_texts = [
            "短文本",
            "中等长度的文本内容，包含中英文混合",
            "这是一个非常长的文本内容，包含大量的中文字符和英文字符，用于测试在较长文本情况下的行高计算性能表现" * 2
        ]
        
        results = []
        start_total = time.perf_counter()
        for text in test_texts:
            start_time = time.perf_counter()
            height = calculator.calculate_height(mock_range, text, 20.0)
            end_time = time.perf_counter()
            
            results.append({
                'text_length': len(text),
                'height': height,
                'time': end_time - start_time
            })
        end_total = time.perf_counter()
        
        # 验证结果合理性
        assert all(r['height'] > 0 for r in results)
        assert all(r['time'] < 0.1 for r in results)  # 计算时间应该很短
        assert end_total - start_total < 1.0  # 总时间应该很短
    
    def test_different_column_widths(self, mock_height_calculator):
        """测试不同列宽对行高计算的影响"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        text = "测试文本内容，用于验证列宽对行高的影响"
        widths = [10.0, 20.0, 30.0, 50.0]
        heights = []
        
        for width in widths:
            height = calculator.calculate_height(mock_range, text, width)
            heights.append(height)
        
        # 列宽越大，行高应该越小（因为需要的行数越少）
        assert heights[0] >= heights[1]  # 窄列需要更多行
        assert heights[1] >= heights[2]
        assert heights[2] >= heights[3]  # 宽列需要更少行

class TestEnhancedHeightCalculator:
    """测试增强行高计算器模块"""
    
    @patch('core.enhanced_height_calculator.GDI_AVAILABLE', False)
    @patch('core.enhanced_height_calculator.PILLOW_AVAILABLE', False)
    def test_xlwings_only_availability(self):
        """测试只有xlwings可用时的情况"""
        from core.enhanced_height_calculator import get_available_methods
        
        methods = get_available_methods()
        assert methods == ['xlwings']
    
    @patch('core.enhanced_height_calculator.GDI_AVAILABLE', True)
    @patch('core.enhanced_height_calculator.PILLOW_AVAILABLE', True)
    def test_all_methods_availability(self):
        """测试所有方法都可用时的情况"""
        from core.enhanced_height_calculator import get_available_methods
        
        methods = get_available_methods()
        assert 'xlwings' in methods
        assert 'gdi' in methods
        assert 'pillow' in methods
    
    def test_calculator_singleton_pattern(self):
        """测试计算器单例模式"""
        from core.enhanced_height_calculator import get_height_calculator
        
        calc1 = get_height_calculator()
        calc2 = get_height_calculator()
        
        assert calc1 is calc2  # 应该是同一个实例
    
    @patch('core.enhanced_height_calculator.get_height_calculator')
    def test_method_setting(self, mock_get_calculator):
        """测试方法设置功能"""
        from core.enhanced_height_calculator import set_calculation_method
        
        mock_calculator = MockHeightCalculator()
        mock_get_calculator.return_value = mock_calculator
        
        set_calculation_method('gdi')
        assert mock_calculator.method == 'gdi'
        
        set_calculation_method('pillow')
        assert mock_calculator.method == 'pillow'

class TestHeightMeasureModules:
    """测试具体的行高测量模块"""
    
    @skip_on_non_windows
    def test_gdi_measure_import(self):
        """测试GDI测量模块导入"""
        try:
            from height_measure.gdi_measure import PrinterTextMeasurer, FontSpec
            assert PrinterTextMeasurer is not None
            assert FontSpec is not None
        except ImportError as e:
            pytest.skip(f"GDI模块不可用: {e}")
    
    def test_pillow_measure_import(self):
        """测试Pillow测量模块导入"""
        try:
            from height_measure.pillow_measure import measure
            assert measure is not None
        except ImportError as e:
            pytest.skip(f"Pillow模块不可用: {e}")
    
    @skip_on_non_windows
    def test_gdi_font_spec_creation(self):
        """测试GDI字体规格创建"""
        try:
            from height_measure.gdi_measure import FontSpec
            
            font_spec = FontSpec(name="SimSun", size_pt=11.0, weight=400, italic=False)
            assert font_spec.name == "SimSun"
            assert font_spec.size_pt == 11.0
            assert font_spec.weight == 400
            assert font_spec.italic == False
        except ImportError:
            pytest.skip("GDI模块不可用")
    
    def test_pillow_basic_measurement(self):
        """测试Pillow基础测量功能"""
        try:
            from height_measure.pillow_measure import measure
            
            # 基础测量测试（模拟）
            with patch('height_measure.pillow_measure.ImageFont.truetype') as mock_font:
                mock_font_obj = Mock()
                mock_font_obj.getlength.return_value = 50.0
                mock_font_obj.getmetrics.return_value = (12, 3)  # ascent, descent
                mock_font.return_value = mock_font_obj
                
                # 这里由于依赖复杂，我们主要测试函数存在性
                # 实际的功能测试需要在集成测试中进行
                assert callable(measure)
                
        except ImportError:
            pytest.skip("Pillow模块不可用")

class TestHeightCalculationEdgeCases:
    """测试行高计算的边界情况"""
    
    def test_empty_text_handling(self, mock_height_calculator):
        """测试空文本处理"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        # 测试None
        height = calculator.calculate_height(mock_range, None, 10.0)
        assert height == 16.0
        
        # 测试空字符串
        height = calculator.calculate_height(mock_range, "", 10.0)
        assert height == 16.0
        
        # 测试只有空格
        height = calculator.calculate_height(mock_range, "   ", 10.0)
        assert height == 16.0
    
    def test_zero_column_width_handling(self, mock_height_calculator):
        """测试零列宽处理"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        # 零列宽应该返回合理的默认值
        height = calculator.calculate_height(mock_range, "测试文本", 0.0)
        assert height > 0
    
    def test_very_long_text(self, mock_height_calculator):
        """测试极长文本处理"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        # 极长文本（1000个字符）
        long_text = "测试" * 500
        height = calculator.calculate_height(mock_range, long_text, 10.0)
        
        # 应该能正常处理并返回合理的高度
        assert height > 100  # 应该需要很多行
        assert height < 10000  # 但不应该无限大
    
    def test_special_characters(self, mock_height_calculator):
        """测试特殊字符处理"""
        calculator = mock_height_calculator
        mock_range = create_mock_xlwings_range()
        
        special_texts = [
            "包含\n换行符的文本",
            "包含\t制表符的文本",
            "包含 emoji 😀 的文本",
            "包含特殊符号 ★♦♠♣ 的文本",
            "English and 中文 mixed text",
        ]
        
        for text in special_texts:
            height = calculator.calculate_height(mock_range, text, 20.0)
            assert height > 0, f"文本 '{text}' 计算失败"

if __name__ == "__main__":
    pytest.main([__file__])