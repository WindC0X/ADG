#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enhanced_height_calculator.py
增强的行高计算器，支持三种方案：
1. 原始xlwings AutoFit方案（默认）
2. GDI精确测量方案
3. Pillow独立计算方案
"""

import logging
import time
from typing import Tuple, Optional
import sys
import os

# 添加父目录到Python路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

try:
    from height_measure.gdi_measure import PrinterTextMeasurer, FontSpec
    GDI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"GDI方案不可用: {e}")
    GDI_AVAILABLE = False

try:
    from height_measure.pillow_measure import measure
    PILLOW_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Pillow方案不可用: {e}")
    PILLOW_AVAILABLE = False

class HeightCalculator:
    """增强的行高计算器"""
    
    def __init__(self):
        global GDI_AVAILABLE, PILLOW_AVAILABLE
        self.gdi_measurer = None
        self.font_spec = None
        self.method = "xlwings"  # 默认使用原始方案
        self.performance_stats = {
            'xlwings': {'count': 0, 'total_time': 0},
            'gdi': {'count': 0, 'total_time': 0},
            'pillow': {'count': 0, 'total_time': 0}
        }
        
        # 初始化GDI组件
        if GDI_AVAILABLE:
            try:
                self.gdi_measurer = PrinterTextMeasurer()
                self.font_spec = FontSpec(name="SimSun", size_pt=11.0, weight=400, italic=False)
                # GDI方案初始化成功，生产环境不显示详细信息
            except Exception as e:
                logging.error(f"GDI方案初始化失败: {e}")
                GDI_AVAILABLE = False
        

    
    def set_method(self, method: str):
        """设置计算方法"""
        global GDI_AVAILABLE, PILLOW_AVAILABLE
        if method not in ['xlwings', 'gdi', 'pillow']:
            raise ValueError("方法必须是: xlwings, gdi, pillow")
        
        if method == 'gdi' and not GDI_AVAILABLE:
            raise RuntimeError("GDI方案不可用")
        
        if method == 'pillow' and not PILLOW_AVAILABLE:
            raise RuntimeError("Pillow方案不可用")
        
        self.method = method
        # 方案切换成功，生产环境不显示详细信息
    
    def calculate_height_xlwings(self, rng, text: str, column_width: float) -> float:
        """使用xlwings AutoFit计算行高"""
        start_time = time.perf_counter()
        
        try:
            # 原始xlwings方法
            rng.value = text
            rng.autofit()
            height = rng.row_height
            
            # 记录性能
            elapsed = time.perf_counter() - start_time
            self.performance_stats['xlwings']['count'] += 1
            self.performance_stats['xlwings']['total_time'] += elapsed
            
            return height
            
        except Exception as e:
            logging.error(f"xlwings方案计算失败: {e}")
            return 64.0  # 返回默认行高
    
    def calculate_height_gdi(self, text: str, column_width: float, row_info: str = "") -> float:
        """使用GDI方案计算行高"""
        if not GDI_AVAILABLE or not self.gdi_measurer:
            raise RuntimeError("GDI方案不可用")
        
        start_time = time.perf_counter()
        
        try:
            # 使用GDI测量器的excel列宽方法，避免二次放大            
            with self.gdi_measurer:
                height_pt, lines = self.gdi_measurer.measure_for_excel_col(
                    text=text,
                    col_width_chars=column_width,
                    spec=self.font_spec,
                    strategy="safe",  # 启用edge保护，避免边界溢出
                    debug=False,  # 生产环境关闭调试输出
                    row_info=row_info  # 传递行号信息
                )
            
            # 记录性能
            elapsed = time.perf_counter() - start_time
            self.performance_stats['gdi']['count'] += 1
            self.performance_stats['gdi']['total_time'] += elapsed
            
            return height_pt
            
        except Exception as e:
            logging.error(f"GDI方案计算失败: {e}")
            return 64.0  # 返回默认行高
    
    def calculate_height_pillow(self, text: str, column_width: float) -> float:
        """使用Pillow方案计算行高"""
        if not PILLOW_AVAILABLE:
            raise RuntimeError("Pillow方案不可用")
        
        start_time = time.perf_counter()
        
        try:
            # Excel列宽转换为像素（类似GDI的转换逻辑）
            # 1字符宽度 ≈ 7像素（基于Pillow的96 DPI计算）
            width_px = int(column_width * 7)
            
            height, lines = measure(
                text=text,
                width_px=width_px,
                font_path_or_name="C:/Windows/Fonts/simsun.ttc",
                font_size_pt=11.0,
                debug=False  # 生产环境关闭调试输出
            )
            
            # 记录性能
            elapsed = time.perf_counter() - start_time
            self.performance_stats['pillow']['count'] += 1
            self.performance_stats['pillow']['total_time'] += elapsed
            
            return height
            
        except Exception as e:
            logging.error(f"Pillow方案计算失败: {e}")
            return 64.0  # 返回默认行高
    
    def calculate_height(self, rng, text: str, column_width: float, row_info: str = "") -> float:
        """根据当前设置的方法计算行高"""
        if not text or not text.strip():
            return 16.0  # 空文本返回最小行高
        
        if self.method == 'xlwings':
            return self.calculate_height_xlwings(rng, text, column_width)
        elif self.method == 'gdi':
            return self.calculate_height_gdi(text, column_width, row_info)
        elif self.method == 'pillow':
            return self.calculate_height_pillow(text, column_width)
        else:
            raise ValueError(f"未知的计算方法: {self.method}")
    
    def get_performance_stats(self) -> dict:
        """获取性能统计"""
        stats = {}
        for method, data in self.performance_stats.items():
            if data['count'] > 0:
                avg_time = data['total_time'] / data['count']
                stats[method] = {
                    'count': data['count'],
                    'total_time': data['total_time'],
                    'avg_time': avg_time,
                    'calls_per_second': 1.0 / avg_time if avg_time > 0 else 0
                }
            else:
                stats[method] = {
                    'count': 0,
                    'total_time': 0,
                    'avg_time': 0,
                    'calls_per_second': 0
                }
        return stats
    
    def print_performance_report(self):
        """打印性能报告"""
        print("\n=== 行高计算性能报告 ===")
        stats = self.get_performance_stats()
        
        for method, data in stats.items():
            if data['count'] > 0:
                print(f"\n{method.upper()}方案:")
                print(f"  调用次数: {data['count']}")
                print(f"  总时间: {data['total_time']:.4f}秒")
                print(f"  平均时间: {data['avg_time']:.6f}秒/次")
                print(f"  处理速度: {data['calls_per_second']:.1f}次/秒")
            else:
                print(f"\n{method.upper()}方案: 未使用")
    
    def reset_stats(self):
        """重置性能统计"""
        for method in self.performance_stats:
            self.performance_stats[method]['count'] = 0
            self.performance_stats[method]['total_time'] = 0
        logging.info("性能统计已重置")
    
    def cleanup(self):
        """清理资源"""
        if self.gdi_measurer:
            # GDI使用上下文管理器，不需要手动清理
            pass
        logging.info("行高计算器资源已清理")

# 全局实例
_height_calculator = None

def get_height_calculator() -> HeightCalculator:
    """获取全局行高计算器实例"""
    global _height_calculator
    if _height_calculator is None:
        _height_calculator = HeightCalculator()
    return _height_calculator

def set_calculation_method(method: str):
    """设置全局计算方法"""
    calculator = get_height_calculator()
    calculator.set_method(method)

def get_available_methods() -> list:
    """获取可用的计算方法"""
    global GDI_AVAILABLE, PILLOW_AVAILABLE
    methods = ['xlwings']  # xlwings总是可用
    if GDI_AVAILABLE:
        methods.append('gdi')
    if PILLOW_AVAILABLE:
        methods.append('pillow')
    return methods

def print_available_methods():
    """打印可用方法"""
    methods = get_available_methods()
    print(f"可用的行高计算方法: {', '.join(methods)}")
    calculator = get_height_calculator()
    print(f"当前使用方法: {calculator.method}")