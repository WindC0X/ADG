# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个档案目录生成器（ADG - Archive Directory Generator），用于生成各种类型的档案目录Excel文件。项目提供Tkinter图形界面，支持多种行高计算方案以确保Excel打印时的精确排版。

## 运行命令

### 启动应用程序
```bash
python main.py
```

### 安装依赖
```bash
pip install -r requirements.txt
```

### 测试行高计算模块
```bash
# 测试GDI方案
python height_measure/gdi_measure.py

# 测试Pillow方案  
python height_measure/pillow_measure.py
```

## 架构概述

### 核心模块结构
- **main.py**: Tkinter GUI主界面，提供用户交互和参数配置
- **core/**: 核心业务逻辑
  - `enhanced_height_calculator.py`: 多方案行高计算器（xlwings/GDI/Pillow）
  - `generator.py`: Excel目录生成核心逻辑，包含分页算法和格式化
  - `transform_excel.py`: Excel文件格式转换工具
- **height_measure/**: 精确行高测量模块
  - `gdi_measure.py`: Windows GDI API精确测量（完美匹配打印预览）
  - `pillow_measure.py`: 基于Pillow的独立计算方案
- **utils/**: 业务配方和工具函数
  - `recipes.py`: 不同类型目录的生成配方（全引目录、案卷目录、卷内目录、简化目录）

### 行高计算架构
项目核心特色是支持三种行高计算方案：
1. **xlwings方案**: 使用Excel原生AutoFit，速度快但打印时可能溢出
2. **GDI方案**: 使用Windows GDI API精确测量，0.0pt误差匹配打印预览
3. **Pillow方案**: 独立计算，无需Office和打印机依赖，高精度

方案通过`enhanced_height_calculator.py`统一管理，支持运行时切换。

### 分页算法
采用全twip精度分页算法（`generator.py:411-454`），精确控制每页内容高度：
- 支持A4纸张横向/纵向自动检测
- 考虑页边距、页脚边距、缩放系数
- 使用共用网格线优化（GRID_TWIP = 15）
- 自动填充空行对齐页面底部

## 开发指南

### 添加新的目录类型
1. 在`utils/recipes.py`中添加新的配方函数
2. 定义列映射和自适应列配置
3. 在`main.py`的GUI中添加对应选项

### 扩展行高计算方案
1. 在`height_measure/`目录下实现新的测量模块
2. 在`enhanced_height_calculator.py`中注册新方案
3. 更新`get_available_methods()`函数

### 调试分页问题
启用详细日志查看分页决策过程：
```python
logging.basicConfig(level=logging.INFO)
```
关键日志位置：`generator.py:442` 分页符插入信息

### 性能优化
- 行高计算器内置性能统计功能
- 使用`calculator.get_performance_stats()`查看各方案耗时
- GDI方案精度最高但相对较慢，Pillow方案部署最简单

## 文件依赖关系

- 模板文件：Excel模板，定义目录格式和样式
- 数据源：包含档案信息的Excel文件（支持.xls自动转换）
- 输出文件夹：生成的目录文件存放位置

## 重要常量

### 精度计算常量（generator.py）
```python
MM_PER_PT = 0.3527777778    # 毫米到点的精确转换
TWIP = 20                   # 1点 = 20 twip
GRID_TWIP = 15             # 共用网格线宽度
```

### 字体规格
项目针对SimSun 11pt字体优化，校准数据位于各测量模块的CALIB_TABLE中。