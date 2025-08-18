# Source Tree Structure - Dev Agent Reference

> **注意**: 此文件为dev Agent专用的项目结构规范。完整的架构信息请参考架构文档。

## 项目根目录结构

```
ADG/
├── main.py                      # 主程序入口，Tkinter GUI
├── app_config.json             # 应用程序配置文件
├── requirements.txt            # 生产依赖
├── requirements.lock           # 版本锁定依赖
├── requirements-dev.txt        # 开发依赖
├── setup.cfg                   # 工具配置
├── pyproject.toml             # 项目配置和代码质量工具
├── .pre-commit-config.yaml    # 预提交钩子配置
└── CLAUDE.md                  # AI助手指引文档
```

## 核心代码结构

### core/ - 核心业务逻辑
```
core/
├── enhanced_height_calculator.py   # 多方案行高计算器
├── generator.py                    # Excel目录生成核心
├── transform_excel.py              # Excel格式转换
├── node_interfaces.py              # 节点接口和数据模型
└── node_engine/                    # 节点引擎目录
    ├── base_node.py                # 节点基类
    ├── dag_scheduler.py            # DAG调度器
    ├── task_queue.py               # 任务队列
    └── nodes/                      # 具体节点实现
        ├── file_input_node.py      # 文件输入节点
        ├── data_transform_node.py  # 数据转换节点
        └── file_output_node.py     # 文件输出节点
```

### utils/ - 工具函数和服务
```
utils/
├── recipes.py                   # 目录生成配方
├── config_manager.py            # 配置管理器
├── service_manager.py           # 第三方服务管理
├── credential_manager.py        # 凭据安全管理
├── feature_manager.py           # 特性标志管理
├── validation_schemas.py        # 数据验证模式
├── rbac_models.py              # RBAC权限模型
├── security_manager.py         # 安全管理器
├── jwt_manager.py              # JWT令牌管理
└── session_manager.py          # 会话管理
```

### height_measure/ - 精确行高测量
```
height_measure/
├── __init__.py
├── gdi_measure.py              # Windows GDI API测量
└── pillow_measure.py           # Pillow独立测量
```

### tests/ - 测试套件
```
tests/
├── unit/                       # 单元测试
│   ├── node_engine/           # 节点引擎测试
│   │   ├── test_node_interfaces.py
│   │   ├── test_file_input_node.py
│   │   ├── test_data_transform_node.py
│   │   └── test_file_output_node.py
│   └── security/              # 安全组件测试
└── integration/               # 集成测试
    ├── workflow/              # 工作流测试
    └── security/              # 安全集成测试
```

### docs/ - 文档目录
```
docs/
├── prd/                       # 产品需求文档
│   ├── index.md
│   ├── 01-project-overview.md
│   ├── 02-requirements.md
│   ├── 03-technical-architecture.md
│   └── 04-implementation-plan.md
├── architecture/              # 架构文档
│   ├── index.md
│   ├── 01-core-architecture.md
│   ├── 02-security-architecture.md
│   ├── 03-dependency-management.md
│   ├── 04-development-standards.md
│   ├── 05-api-design.md
│   ├── 06-technical-implementation.md
│   ├── 07-deployment-monitoring.md
│   ├── 08-risk-management.md
│   ├── 09-project-management.md
│   ├── 10-documentation-guide.md
│   ├── coding-standards.md      # Dev Agent编码标准
│   ├── tech-stack.md           # Dev Agent技术栈
│   └── source-tree.md          # Dev Agent项目结构
└── stories/                   # 用户故事
    ├── 1.1.platform-refactoring-foundation.md
    └── 1.2.establish-rbac-access-control.md
```

## 文件命名约定

### Python模块命名
- **模块文件**: `lowercase_with_underscores.py`
- **测试文件**: `test_module_name.py`
- **配置文件**: `config_name.py`

### 类和函数组织
```python
# 每个模块的标准结构
"""模块文档字符串"""

# 1. 标准库导入
import os
import sys

# 2. 第三方库导入  
import pandas as pd
from dataclasses import dataclass

# 3. 本地导入
from core.node_interfaces import ProcessingNode
from utils.validation_schemas import NodeSchema

# 4. 常量定义
DEFAULT_TIMEOUT = 30

# 5. 类定义
class ExampleNode(ProcessingNode):
    pass

# 6. 函数定义
def helper_function():
    pass

# 7. 主程序块
if __name__ == "__main__":
    pass
```

## 目录组织原则

### 1. 按功能职责划分
- `core/` - 核心业务逻辑
- `utils/` - 通用工具和服务
- `height_measure/` - 专业计算模块

### 2. 按使用场景组织
- `docs/architecture/` - 按开发需求组织架构文档
- `tests/` - 按测试类型和覆盖模块组织

### 3. 配置文件集中管理
- 根目录: 主要配置文件
- `.bmad-core/` - BMad工作流配置

### 4. 扩展性考虑
- 新增节点类型: `core/node_engine/nodes/`
- 新增工具模块: `utils/`
- 新增测试: `tests/unit/` 或 `tests/integration/`

---

**详细项目架构**: `docs/architecture/01-core-architecture.md`