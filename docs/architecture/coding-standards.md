# Coding Standards - Dev Agent Reference

> **注意**: 此文件为dev Agent专用的编码标准快速参考。完整的开发规范请参考 `04-development-standards.md`。

## Python编码标准

### 项目配置标准 (pyproject.toml)

```toml
[build-system]
requires = ["setuptools>=45", "wheel", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
name = "adg-platform"
version = "1.0.0"
description = "ADG Intelligent Archive Directory Platform"
requires-python = ">=3.11.0"

# Black配置 - 代码格式化
[tool.black]
line-length = 88
target-version = ["py311"]
include = '\.pyi?$'

# isort配置 - 导入排序  
[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88
known_first_party = ["core", "utils", "height_measure"]
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]

# MyPy配置 - 类型检查
[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_optional = true
strict_equality = true

# Pytest配置 - 测试框架
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: unit tests",
    "integration: integration tests", 
    "performance: performance tests",
    "smoke: smoke tests"
]

# Coverage配置 - 测试覆盖率
[tool.coverage.run]
source = ["core", "utils", "height_measure"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
show_missing = true
precision = 2
```

## 核心编码规范

### 命名约定
- **模块/包**: `lowercase_with_underscores`
- **类名**: `PascalCase` 
- **函数/方法**: `lowercase_with_underscores`
- **变量**: `lowercase_with_underscores`
- **常量**: `ALL_CAPS_WITH_UNDERSCORES`
- **私有成员**: `_single_leading_underscore`

### 类型注解要求
```python
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ArchiveDocument:
    id: str
    title: str
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
def process_document(document: ArchiveDocument) -> Dict[str, Any]:
    """所有函数必须包含类型注解和文档字符串"""
    pass
```

### 文档字符串标准
```python
def example_function(param1: str, param2: int) -> bool:
    """简洁描述函数功能。
    
    Args:
        param1: 参数1描述
        param2: 参数2描述
        
    Returns:
        返回值描述
        
    Raises:
        ExceptionType: 异常描述
    """
```

### 测试标准
- 单元测试覆盖率 ≥ 85%
- 测试文件命名: `test_*.py`
- 测试类命名: `TestClassName`  
- 测试方法命名: `test_method_name`
- 使用pytest标记分类测试

### 代码质量工具
**必须通过的检查**:
- `black` - 代码格式化
- `isort` - 导入排序
- `flake8` - 代码风格检查
- `mypy` - 类型检查
- `pytest` - 单元测试

---

**详细标准文档**: `docs/architecture/04-development-standards.md`