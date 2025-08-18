# ADG项目测试要求

## 安装测试依赖

```bash
pip install pytest pytest-cov psutil
```

## 可选依赖（用于完整功能测试）

```bash
# Windows下的GDI测试支持
pip install pywin32

# 图像处理测试支持
pip install Pillow

# GUI自动化测试支持（高级功能）
pip install pytest-qt
```

## 运行测试

### 基本测试命令

```bash
# 快速冒烟测试（推荐，30秒内完成）
python tests/run_tests.py smoke

# 完整单元测试
python tests/run_tests.py unit

# 集成测试
python tests/run_tests.py integration

# 性能基准测试
python tests/run_tests.py performance

# GUI功能测试
python tests/run_tests.py gui

# 运行所有测试
python tests/run_tests.py all

# 测试覆盖率分析
python tests/run_tests.py coverage
```

### 高级测试选项

```bash
# 快速模式（跳过耗时测试）
python tests/run_tests.py all --quick

# 运行特定测试
python tests/run_tests.py --specific tests/test_height_calculation.py

# 运行特定测试函数
python tests/run_tests.py --specific tests/test_config_manager.py::TestConfigManager::test_save_and_load_config

# 详细输出
python tests/run_tests.py unit --verbose
```

## 测试类型说明

### 1. 冒烟测试 (smoke)
- **执行时间**: < 30秒
- **覆盖范围**: 核心功能基本验证
- **适用场景**: 快速回归检查，CI/CD流水线

### 2. 单元测试 (unit)
- **执行时间**: 1-3分钟
- **覆盖范围**: 
  - 行高计算模块 (height_calculation)
  - 配置管理器 (config_manager)
  - 核心生成器 (generator)
- **适用场景**: 开发过程中的功能验证

### 3. 集成测试 (integration)
- **执行时间**: 2-5分钟
- **覆盖范围**: 
  - 业务配方完整流程 (recipes)
  - 模块间交互验证
- **适用场景**: 功能集成验证

### 4. 性能测试 (performance)
- **执行时间**: 3-10分钟
- **覆盖范围**: 
  - 行高计算性能
  - 数据处理性能
  - 内存使用分析
  - 端到端性能
- **适用场景**: 性能回归检测，优化验证

### 5. GUI测试 (gui)
- **执行时间**: 1-2分钟
- **覆盖范围**: 
  - 界面交互逻辑
  - 状态管理
  - 任务控制
- **适用场景**: 用户界面功能验证

## 测试环境配置

### 环境变量

```bash
# 快速模式（减少测试迭代次数）
set ADG_QUICK_MODE=1

# 测试超时设置（秒）
set ADG_TEST_TIMEOUT=60

# 禁用GUI实际启动（测试模拟模式）
set ADG_MOCK_GUI=1
```

### 测试配置文件

测试配置在 `tests/conftest.py` 中定义：

```python
TEST_CONFIG = {
    'timeout': 30,  # 测试超时时间（秒）
    'temp_dir_prefix': 'adg_test_',
    'log_level': logging.WARNING,  # 测试时减少日志噪音
    'mock_excel': True,  # 是否模拟Excel操作
    'benchmark_iterations': 3,  # 性能测试迭代次数
}
```

## 测试数据和模拟

### 模拟数据
- 自动生成模拟档案数据
- 模拟Excel模板文件
- 模拟行高计算器
- 模拟打印服务

### 临时文件管理
- 自动创建和清理临时目录
- 测试隔离，避免相互影响
- 安全的文件路径验证

## 持续集成建议

### GitHub Actions / Azure DevOps

```yaml
# 基本CI流程
- name: Install dependencies
  run: pip install -r requirements.txt pytest pytest-cov

- name: Run smoke tests
  run: python tests/run_tests.py smoke

- name: Run unit tests
  run: python tests/run_tests.py unit

# 性能基线检查（可选）
- name: Performance regression check
  run: python tests/run_tests.py performance
```

### 本地开发工作流

```bash
# 开发前：快速检查
python tests/run_tests.py smoke

# 功能开发中：单元测试
python tests/run_tests.py unit

# 提交前：完整测试
python tests/run_tests.py all --quick

# 发布前：完整验证
python tests/run_tests.py all
python tests/run_tests.py coverage
```

## 性能基线管理

### 建立性能基线

```bash
# 首次运行性能测试，建立基线
python tests/run_tests.py performance

# 基线文件保存在：tests/performance_baseline.json
```

### 性能回归检测

性能测试会自动与基线对比：
- 容忍度：±20%
- 超出容忍度会报告性能退化
- 基线文件应纳入版本控制

## 故障排除

### 常见问题

1. **ImportError: No module named 'win32api'**
   ```bash
   pip install pywin32
   ```

2. **测试超时**
   ```bash
   # 增加超时时间
   python tests/run_tests.py unit --quick
   ```

3. **权限错误**
   - 确保临时目录有写入权限
   - Windows下可能需要管理员权限运行

4. **内存不足**
   ```bash
   # 使用快速模式减少内存使用
   python tests/run_tests.py performance --quick
   ```

### 调试测试

```bash
# 详细输出调试信息
python tests/run_tests.py unit -v

# 在第一个失败处停止
pytest tests/ -x

# 显示本地变量
pytest tests/ --tb=long
```

## 测试报告

### 覆盖率报告

运行 `python tests/run_tests.py coverage` 后：
- HTML报告：`htmlcov/index.html`
- 控制台报告：显示缺失覆盖的行

### 性能报告

性能测试会生成：
- 控制台实时输出
- JSON格式基线文件
- 性能对比分析

## 扩展测试

### 添加新测试

1. 在 `tests/` 目录下创建 `test_*.py` 文件
2. 使用 `tests/conftest.py` 中的公共fixtures
3. 遵循命名约定：`test_功能描述`
4. 添加适当的性能测试和基准

### 自定义测试配置

修改 `tests/conftest.py` 中的 `TEST_CONFIG` 字典来调整测试行为。