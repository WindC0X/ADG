"""
性能基准测试框架
用于监控核心功能的性能表现，确保重构过程中性能不退化
"""

import pytest
import sys
import os
import time
import statistics
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import (
    TEST_CONFIG,
    benchmark,
    create_mock_archive_data,
    create_mock_template,
    MockHeightCalculator
)

@dataclass
class PerformanceMetric:
    """性能指标数据结构"""
    name: str
    value: float
    unit: str
    description: str
    timestamp: float
    
@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    iterations: int
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    std_dev: float
    metrics: List[PerformanceMetric]
    metadata: Dict[str, Any]

class PerformanceBenchmark:
    """性能基准测试基础类"""
    
    def __init__(self, name: str, iterations: int = None):
        self.name = name
        self.iterations = iterations or TEST_CONFIG['benchmark_iterations']
        self.results: List[BenchmarkResult] = []
        self.baseline_file = Path(__file__).parent / 'performance_baseline.json'
    
    def run_benchmark(self, func, *args, **kwargs) -> BenchmarkResult:
        """运行性能基准测试"""
        times = []
        metrics = []
        
        print(f"\n🚀 运行性能基准测试: {self.name}")
        print(f"📊 迭代次数: {self.iterations}")
        
        for i in range(self.iterations):
            print(f"⏱️  迭代 {i+1}/{self.iterations}...", end=" ")
            
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            
            elapsed = end_time - start_time
            times.append(elapsed)
            
            print(f"{elapsed:.4f}s")
            
            # 收集额外指标
            if isinstance(result, dict) and 'metrics' in result:
                metrics.extend(result['metrics'])
        
        # 计算统计数据
        min_time = min(times)
        max_time = max(times)
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0.0
        
        # 创建结果对象
        benchmark_result = BenchmarkResult(
            test_name=self.name,
            iterations=self.iterations,
            min_time=min_time,
            max_time=max_time,
            avg_time=avg_time,
            median_time=median_time,
            std_dev=std_dev,
            metrics=metrics,
            metadata={
                'timestamp': time.time(),
                'python_version': sys.version,
                'test_config': TEST_CONFIG
            }
        )
        
        self.results.append(benchmark_result)
        self._print_results(benchmark_result)
        
        return benchmark_result
    
    def _print_results(self, result: BenchmarkResult):
        """打印基准测试结果"""
        print(f"\n📈 性能基准测试结果 - {result.test_name}")
        print("=" * 50)
        print(f"🔄 迭代次数: {result.iterations}")
        print(f"⚡ 最快时间: {result.min_time:.4f}s")
        print(f"🐌 最慢时间: {result.max_time:.4f}s")
        print(f"📊 平均时间: {result.avg_time:.4f}s")
        print(f"📍 中位时间: {result.median_time:.4f}s")
        print(f"📏 标准差:   {result.std_dev:.4f}s")
        
        if result.metrics:
            print(f"\n📋 额外指标:")
            for metric in result.metrics:
                print(f"  • {metric.name}: {metric.value:.4f} {metric.unit}")
        
        print("=" * 50)
    
    def save_baseline(self, filename: str = None):
        """保存性能基线"""
        baseline_file = Path(filename) if filename else self.baseline_file
        
        baseline_data = {
            'timestamp': time.time(),
            'results': [asdict(result) for result in self.results]
        }
        
        baseline_file.parent.mkdir(exist_ok=True)
        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 性能基线已保存到: {baseline_file}")
    
    def load_baseline(self, filename: str = None) -> Dict[str, Any]:
        """加载性能基线"""
        baseline_file = Path(filename) if filename else self.baseline_file
        
        if not baseline_file.exists():
            print(f"⚠️  基线文件不存在: {baseline_file}")
            return {}
        
        with open(baseline_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def compare_with_baseline(self, tolerance: float = 0.2) -> bool:
        """与基线进行性能对比"""
        baseline_data = self.load_baseline()
        
        if not baseline_data or not self.results:
            print("⚠️  无法进行基线对比：缺少基线数据或当前结果")
            return True
        
        print(f"\n🔍 性能对比分析 (容忍度: ±{tolerance*100:.1f}%)")
        print("=" * 60)
        
        baseline_results = {r['test_name']: r for r in baseline_data['results']}
        all_passed = True
        
        for current_result in self.results:
            test_name = current_result.test_name
            baseline_result = baseline_results.get(test_name)
            
            if not baseline_result:
                print(f"🆕 新测试: {test_name} - {current_result.avg_time:.4f}s")
                continue
            
            baseline_avg = baseline_result['avg_time']
            current_avg = current_result.avg_time
            change_ratio = (current_avg - baseline_avg) / baseline_avg
            
            status = "✅ 通过"
            if abs(change_ratio) > tolerance:
                status = "❌ 性能退化" if change_ratio > 0 else "🚀 性能提升"
                if change_ratio > tolerance:
                    all_passed = False
            
            print(f"{status} {test_name}:")
            print(f"  基线: {baseline_avg:.4f}s")
            print(f"  当前: {current_avg:.4f}s")
            print(f"  变化: {change_ratio:+.2%}")
            print()
        
        return all_passed

class TestHeightCalculationPerformance:
    """行高计算性能测试"""
    
    def test_height_calculation_benchmark(self):
        """行高计算性能基准测试"""
        benchmark = PerformanceBenchmark("height_calculation", iterations=50)
        
        def height_calc_test():
            calculator = MockHeightCalculator()
            
            # 测试不同复杂度的文本
            test_cases = [
                ("短文本", 20.0),
                ("中等长度的文本内容，包含中英文混合字符", 15.0),
                ("这是一个非常长的文本内容，包含大量的中文字符和英文字符，用于测试在较长文本情况下的行高计算性能表现。" * 3, 10.0)
            ]
            
            start_time = time.perf_counter()
            calculations = 0
            
            for text, width in test_cases:
                from tests.conftest import create_mock_xlwings_range
                mock_range = create_mock_xlwings_range()
                
                # 测试三种计算方法
                for method in ['xlwings', 'gdi', 'pillow']:
                    calculator.set_method(method)
                    height = calculator.calculate_height(mock_range, text, width)
                    calculations += 1
            
            total_time = time.perf_counter() - start_time
            
            stats = calculator.get_performance_stats()
            
            return {
                'calculations': calculations,
                'total_time': total_time,
                'metrics': [
                    PerformanceMetric(
                        name=f"{method}_avg_time",
                        value=data['avg_time'],
                        unit="s",
                        description=f"{method}方法平均计算时间",
                        timestamp=time.time()
                    )
                    for method, data in stats.items() if data['count'] > 0
                ]
            }
        
        result = benchmark.run_benchmark(height_calc_test)
        assert result.avg_time < 1.0  # 应该在1秒内完成
        return result

class TestDataProcessingPerformance:
    """数据处理性能测试"""
    
    def test_large_dataset_processing(self, test_env):
        """大数据集处理性能测试"""
        benchmark = PerformanceBenchmark("large_dataset_processing", iterations=5)
        
        def data_processing_test():
            # 创建大型数据集
            large_data = create_mock_archive_data(1000)  # 1000条记录
            
            start_time = time.perf_counter()
            
            # 模拟数据处理操作
            processed_groups = {}
            for _, row in large_data.iterrows():
                archive_id = row['案卷档号']
                if archive_id not in processed_groups:
                    processed_groups[archive_id] = []
                processed_groups[archive_id].append(row)
            
            # 模拟数据过滤和排序
            filtered_data = large_data[large_data['页数'].astype(int) > 0]
            sorted_data = filtered_data.sort_values('案卷档号')
            
            processing_time = time.perf_counter() - start_time
            
            return {
                'processed_records': len(large_data),
                'unique_archives': len(processed_groups),
                'filtered_records': len(filtered_data),
                'processing_time': processing_time,
                'metrics': [
                    PerformanceMetric(
                        name="records_per_second",
                        value=len(large_data) / processing_time,
                        unit="records/s",
                        description="每秒处理记录数",
                        timestamp=time.time()
                    )
                ]
            }
        
        result = benchmark.run_benchmark(data_processing_test)
        
        # 验证处理速度
        records_per_second = 1000 / result.avg_time
        assert records_per_second > 100  # 每秒至少处理100条记录
        
        return result
    
    def test_excel_file_operations(self, test_env):
        """Excel文件操作性能测试"""
        benchmark = PerformanceBenchmark("excel_file_operations", iterations=10)
        
        def excel_ops_test():
            # 创建测试数据
            test_data = create_mock_archive_data(100)
            
            start_time = time.perf_counter()
            
            # Excel写入操作
            excel_path = os.path.join(test_env.temp_dir, 'perf_test.xlsx')
            test_data.to_excel(excel_path, index=False)
            
            # Excel读取操作
            loaded_data = pd.read_excel(excel_path)
            
            # 数据验证
            assert len(loaded_data) == len(test_data)
            assert list(loaded_data.columns) == list(test_data.columns)
            
            file_ops_time = time.perf_counter() - start_time
            
            # 获取文件大小
            file_size = os.path.getsize(excel_path)
            
            return {
                'file_size': file_size,
                'records': len(test_data),
                'ops_time': file_ops_time,
                'metrics': [
                    PerformanceMetric(
                        name="file_size",
                        value=file_size / 1024,
                        unit="KB",
                        description="生成文件大小",
                        timestamp=time.time()
                    ),
                    PerformanceMetric(
                        name="throughput",
                        value=len(test_data) / file_ops_time,
                        unit="records/s",
                        description="文件操作吞吐量",
                        timestamp=time.time()
                    )
                ]
            }
        
        result = benchmark.run_benchmark(excel_ops_test)
        assert result.avg_time < 5.0  # Excel操作应该在5秒内完成
        return result

class TestMemoryUsagePerformance:
    """内存使用性能测试"""
    
    def test_memory_efficiency(self):
        """内存效率测试"""
        import psutil
        import gc
        
        benchmark = PerformanceBenchmark("memory_efficiency", iterations=3)
        
        def memory_test():
            process = psutil.Process()
            
            # 记录初始内存
            gc.collect()  # 强制垃圾回收
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 创建大量数据
            large_datasets = []
            for i in range(10):
                data = create_mock_archive_data(500)
                large_datasets.append(data)
            
            # 记录峰值内存
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 清理数据
            del large_datasets
            gc.collect()
            
            # 记录清理后内存
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            memory_used = peak_memory - initial_memory
            memory_leaked = final_memory - initial_memory
            
            return {
                'initial_memory': initial_memory,
                'peak_memory': peak_memory,
                'final_memory': final_memory,
                'memory_used': memory_used,
                'memory_leaked': memory_leaked,
                'metrics': [
                    PerformanceMetric(
                        name="memory_usage",
                        value=memory_used,
                        unit="MB",
                        description="内存使用量",
                        timestamp=time.time()
                    ),
                    PerformanceMetric(
                        name="memory_leak",
                        value=memory_leaked,
                        unit="MB",
                        description="内存泄漏量",
                        timestamp=time.time()
                    )
                ]
            }
        
        result = benchmark.run_benchmark(memory_test)
        
        # 内存泄漏应该很少
        assert all(m.value < 50 for m in result.metrics if m.name == "memory_leak")
        
        return result

class TestConfigurationPerformance:
    """配置操作性能测试"""
    
    def test_config_operations_benchmark(self, test_env):
        """配置操作性能基准测试"""
        benchmark = PerformanceBenchmark("config_operations", iterations=20)
        
        def config_ops_test():
            from utils.config_manager import ConfigManager
            
            config_file = os.path.join(test_env.temp_dir, 'perf_config.json')
            manager = ConfigManager(config_file)
            
            start_time = time.perf_counter()
            
            # 批量配置操作
            operations = 0
            
            # 设置操作
            for i in range(100):
                manager.set_path('template_path', f'/test/template_{i}.xlsx')
                manager.set_option('start_file', f'FILE_{i:03d}')
                manager.set_last_recipe('案卷目录')
                operations += 3
            
            # 保存操作
            manager.save_config()
            operations += 1
            
            # 读取操作
            for i in range(100):
                template_path = manager.get('paths.template_path')
                start_file = manager.get('options.start_file')
                recipe = manager.get_last_recipe()
                operations += 3
            
            ops_time = time.perf_counter() - start_time
            
            return {
                'operations': operations,
                'ops_time': ops_time,
                'metrics': [
                    PerformanceMetric(
                        name="ops_per_second",
                        value=operations / ops_time,
                        unit="ops/s",
                        description="每秒配置操作数",
                        timestamp=time.time()
                    )
                ]
            }
        
        result = benchmark.run_benchmark(config_ops_test)
        
        # 配置操作应该很快
        ops_per_second = result.metrics[0].value if result.metrics else 0
        assert ops_per_second > 1000  # 每秒至少1000次操作
        
        return result

class TestOverallSystemPerformance:
    """整体系统性能测试"""
    
    def test_end_to_end_performance(self, test_env):
        """端到端性能测试"""
        benchmark = PerformanceBenchmark("end_to_end_system", iterations=3)
        
        def e2e_test():
            from unittest.mock import patch, Mock
            
            start_time = time.perf_counter()
            
            # 模拟完整的目录生成流程
            with patch('utils.recipes.load_data') as mock_load_data, \
                 patch('utils.recipes.prepare_template') as mock_prepare_template, \
                 patch('utils.recipes.generate_one_archive_directory') as mock_generate, \
                 patch('utils.recipes.get_subset') as mock_get_subset, \
                 patch('utils.recipes.cleanup_stream') as mock_cleanup, \
                 patch('utils.recipes.xw.App') as mock_app:
                
                from utils.recipes import create_jn_or_jh_index
                
                # 设置模拟数据
                mock_data = create_mock_archive_data(50)
                mock_load_data.return_value = mock_data
                mock_prepare_template.return_value = Mock()
                mock_get_subset.return_value = mock_data['案卷档号'].unique()
                mock_generate.return_value = 2
                
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
                
                # 执行完整流程
                create_jn_or_jh_index(
                    catalog_path='test_catalog.xlsx',
                    template_path='test_template.xlsx',
                    output_folder=test_env.temp_dir,
                    recipe_name='卷内目录'
                )
                
                e2e_time = time.perf_counter() - start_time
                
                return {
                    'e2e_time': e2e_time,
                    'archives_processed': len(mock_data['案卷档号'].unique()),
                    'metrics': [
                        PerformanceMetric(
                            name="archives_per_second",
                            value=len(mock_data['案卷档号'].unique()) / e2e_time,
                            unit="archives/s",
                            description="每秒处理档案数",
                            timestamp=time.time()
                        )
                    ]
                }
        
        result = benchmark.run_benchmark(e2e_test)
        
        # 端到端处理应该在合理时间内完成
        assert result.avg_time < 10.0  # 应该在10秒内完成
        
        # 保存性能基线
        benchmark.save_baseline()
        
        return result

if __name__ == "__main__":
    # 运行所有性能测试
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x"  # 遇到第一个失败就停止
    ])