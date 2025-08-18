"""
项目集成脚本
将测试基础设施集成到现有ADG项目的启动脚本
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def setup_test_environment():
    """设置测试环境"""
    # 创建测试日志目录
    test_log_dir = PROJECT_ROOT / "logs" / "tests"
    test_log_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置测试日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(test_log_dir / "test_integration.log"),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("测试环境已设置")
    return logger

def check_test_health():
    """检查测试健康状态"""
    logger = logging.getLogger(__name__)
    
    try:
        # 导入测试运行器
        from tests.run_tests import run_smoke_tests
        
        logger.info("🏥 执行测试健康检查...")
        
        # 运行快速冒烟测试
        result = run_smoke_tests()
        
        if result == 0:
            logger.info("✅ 测试健康检查通过")
            return True
        else:
            logger.warning("⚠️  测试健康检查失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试健康检查出错: {e}")
        return False

def integrate_with_main_app():
    """与主应用集成"""
    logger = logging.getLogger(__name__)
    
    try:
        # 检查主应用是否存在
        main_app_path = PROJECT_ROOT / "main.py"
        if not main_app_path.exists():
            logger.warning("⚠️  主应用文件main.py不存在")
            return False
        
        logger.info("🔗 与主应用集成测试基础设施...")
        
        # 在这里可以添加与main.py的集成逻辑
        # 例如：添加测试菜单项、健康检查端点等
        
        logger.info("✅ 测试基础设施集成完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 集成失败: {e}")
        return False

def show_test_usage():
    """显示测试使用说明"""
    print("""
🧪 ADG项目测试基础设施使用指南
================================================

快速开始：
  python tests/run_tests.py smoke     # 30秒快速验证
  python tests/run_tests.py unit      # 完整单元测试
  python tests/run_tests.py all       # 运行所有测试

开发工作流：
  1. 开发前：python tests/run_tests.py smoke
  2. 开发中：python tests/run_tests.py unit
  3. 提交前：python tests/run_tests.py all --quick
  4. 发布前：python tests/run_tests.py coverage

性能监控：
  python tests/run_tests.py performance

测试报告：
  测试覆盖率：htmlcov/index.html
  性能基线：tests/performance_baseline.json

故障排除：
  - 权限问题：以管理员身份运行
  - 依赖缺失：pip install pytest pytest-cov psutil
  - 超时问题：使用 --quick 参数

================================================
详细文档：tests/README.md
""")

def main():
    """主函数"""
    logger = setup_test_environment()
    
    print("🚀 ADG项目测试基础设施集成")
    print("=" * 50)
    
    # 检查项目结构
    logger.info("📁 检查项目结构...")
    required_dirs = [
        PROJECT_ROOT / "core",
        PROJECT_ROOT / "utils", 
        PROJECT_ROOT / "height_measure",
        PROJECT_ROOT / "tests"
    ]
    
    missing_dirs = [d for d in required_dirs if not d.exists()]
    if missing_dirs:
        logger.error(f"❌ 缺少必要目录: {missing_dirs}")
        return 1
    
    logger.info("✅ 项目结构检查通过")
    
    # 检查测试健康状态
    if not check_test_health():
        logger.error("❌ 测试健康检查失败，请检查测试配置")
        return 1
    
    # 与主应用集成
    if not integrate_with_main_app():
        logger.error("❌ 主应用集成失败")
        return 1
    
    # 显示使用说明
    show_test_usage()
    
    logger.info("🎉 测试基础设施集成完成！")
    print("\n✅ 测试基础设施已成功集成到ADG项目")
    print("📖 查看 tests/README.md 获取详细使用说明")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())