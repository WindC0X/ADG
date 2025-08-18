"""
测试运行脚本和配置
提供统一的测试执行入口和配置管理
"""

import sys
import os
import pytest
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_unit_tests():
    """运行单元测试"""
    print("🧪 执行单元测试...")
    return pytest.main([
        str(PROJECT_ROOT / "tests" / "test_height_calculation.py"),
        str(PROJECT_ROOT / "tests" / "test_generator.py"),
        str(PROJECT_ROOT / "tests" / "test_config_manager.py"),
        "-v",
        "--tb=short"
    ])

def run_integration_tests():
    """运行集成测试"""
    print("🔗 执行集成测试...")
    return pytest.main([
        str(PROJECT_ROOT / "tests" / "test_recipes_integration.py"),
        "-v",
        "--tb=short"
    ])

def run_performance_tests():
    """运行性能测试"""
    print("⚡ 执行性能测试...")
    return pytest.main([
        str(PROJECT_ROOT / "tests" / "test_performance.py"),
        "-v",
        "--tb=short",
        "-s"  # 显示性能输出
    ])

def run_gui_tests():
    """运行GUI测试"""
    print("🖥️  执行GUI测试...")
    return pytest.main([
        str(PROJECT_ROOT / "tests" / "test_gui_automation.py"),
        "-v",
        "--tb=short"
    ])

def run_all_tests():
    """运行所有测试"""
    print("🚀 执行完整测试套件...")
    return pytest.main([
        str(PROJECT_ROOT / "tests"),
        "-v",
        "--tb=short",
        "--durations=10"  # 显示最慢的10个测试
    ])

def run_smoke_tests():
    """运行冒烟测试（快速验证核心功能）"""
    print("💨 执行冒烟测试...")
    return pytest.main([
        str(PROJECT_ROOT / "tests" / "test_height_calculation.py::TestHeightCalculationMethods::test_mock_calculator_basic_functionality"),
        str(PROJECT_ROOT / "tests" / "test_config_manager.py::TestConfigManager::test_default_config_structure"),
        str(PROJECT_ROOT / "tests" / "test_generator.py::TestGeneratorUtilityFunctions::test_mm_to_twip_conversion"),
        "-v",
        "--tb=short"
    ])

def run_coverage_tests():
    """运行测试覆盖率分析"""
    print("📊 执行测试覆盖率分析...")
    try:
        import pytest_cov
    except ImportError:
        print("❌ 需要安装 pytest-cov: pip install pytest-cov")
        return 1
    
    return pytest.main([
        str(PROJECT_ROOT / "tests"),
        "--cov=" + str(PROJECT_ROOT),
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-exclude=*/tests/*",
        "-v"
    ])

def run_specific_test(test_path):
    """运行指定的测试"""
    print(f"🎯 执行指定测试: {test_path}")
    return pytest.main([
        test_path,
        "-v",
        "--tb=short"
    ])

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ADG项目测试运行器")
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "performance", "gui", "all", "smoke", "coverage"],
        nargs="?",
        default="smoke",
        help="要运行的测试类型 (默认: smoke)"
    )
    parser.add_argument(
        "--specific",
        type=str,
        help="运行特定的测试文件或测试函数"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出"
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="快速模式（跳过耗时测试）"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧪 ADG项目测试套件")
    print("=" * 60)
    
    # 设置环境变量
    if args.quick:
        os.environ["ADG_QUICK_MODE"] = "1"
        print("⚡ 快速模式已启用")
    
    # 检查项目结构
    required_files = [
        PROJECT_ROOT / "main.py",
        PROJECT_ROOT / "core" / "enhanced_height_calculator.py",
        PROJECT_ROOT / "core" / "generator.py",
        PROJECT_ROOT / "utils" / "config_manager.py"
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    if missing_files:
        print("❌ 缺少必要的项目文件:")
        for file in missing_files:
            print(f"   - {file}")
        return 1
    
    # 运行测试
    try:
        if args.specific:
            exit_code = run_specific_test(args.specific)
        elif args.test_type == "unit":
            exit_code = run_unit_tests()
        elif args.test_type == "integration":
            exit_code = run_integration_tests()
        elif args.test_type == "performance":
            exit_code = run_performance_tests()
        elif args.test_type == "gui":
            exit_code = run_gui_tests()
        elif args.test_type == "all":
            exit_code = run_all_tests()
        elif args.test_type == "smoke":
            exit_code = run_smoke_tests()
        elif args.test_type == "coverage":
            exit_code = run_coverage_tests()
        else:
            print(f"❌ 未知的测试类型: {args.test_type}")
            return 1
        
        # 输出结果
        print("\n" + "=" * 60)
        if exit_code == 0:
            print("✅ 所有测试通过!")
        else:
            print("❌ 测试失败!")
        print("=" * 60)
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 测试执行出错: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())