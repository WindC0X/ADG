# Tech Stack - Dev Agent Reference

> **注意**: 此文件为dev Agent专用的技术栈快速参考。完整的架构信息请参考 `01-core-architecture.md`。

## Python运行环境

### 基础要求
- **Python版本**: ≥ 3.11.0
- **操作系统**: Windows (主要), Linux (支持)
- **内存要求**: ≥ 8GB (推荐16GB)

## 核心依赖

### GUI框架
```python
# GUI基础
tkinter  # Python内置GUI库，主界面
```

### 数据处理
```python
# 数据处理核心库
pandas==2.1.4      # 数据操作和分析
numpy==1.25.2       # 数值计算
openpyxl==3.1.2     # Excel文件处理
xlwings==0.30.13    # Excel自动化(仅Windows)
```

### 图像处理
```python
# 行高计算和图像处理
pillow==10.1.0      # 图像处理库
pywin32==306        # Windows API访问
```

### 开发工具
```python
# 代码质量工具
black==23.12.0      # 代码格式化
isort==5.13.2       # 导入排序
flake8==6.1.0       # 代码风格检查
mypy==1.7.1         # 类型检查
pytest==7.4.3      # 测试框架
pytest-cov==4.1.0  # 测试覆盖率
pre-commit==3.6.0   # Git预提交钩子
```

## 技术架构选择

### 数据库
- **SQLite** - 嵌入式数据库，WAL模式
  - 任务队列存储
  - 会话管理
  - 审计日志

### 计算方案
- **行高计算**: 三种方案支持
  - xlwings (Windows Excel API)
  - GDI (Windows API精确测量)  
  - Pillow (跨平台独立计算)

### 节点引擎
- **架构**: DAG (有向无环图)
- **内存预算**: 50MB限制
- **存储**: SQLite WAL模式

## 平台兼容性

### Windows平台 (主要支持)
- Excel集成 (xlwings + pywin32)
- GDI API精确测量
- 完整功能支持

### Linux平台 (基础支持)  
- Pillow行高计算
- 基础Excel处理
- 无GUI自动化功能

## 性能要求

### 内存预算分配
| 组件 | 内存预算 | 用途 |
|------|----------|------|
| 节点引擎 | 50MB | DAG执行和任务队列 |
| 安全组件 | 25MB | 认证和会话管理 |
| Excel处理 | 100MB | 文件处理和计算 |
| GUI界面 | 50MB | 用户界面 |

### 响应时间要求
- 节点处理: < 50ms (非AI节点)
- GUI响应: < 200ms
- 认证操作: < 100ms
- Excel生成: 1000记录 ≤ 3秒 (P95)

## 集成接口

### Excel自动化
- xlwings COM接口 (Windows)
- openpyxl直接读写
- 模板系统支持

### 系统集成
- Windows打印机API
- 文件系统监控
- 进程间通信

---

**详细架构文档**: `docs/architecture/01-core-architecture.md`