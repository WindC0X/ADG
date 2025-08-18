# ADG Intelligent Archive Directory Platform - Architecture Documentation

## 文档概述

这是ADG智能档案目录平台的完整架构文档，涵盖了从核心设计到部署运维的各个方面。

## 文档章节

### 1. [核心架构文档](./01-core-architecture.md)
- 项目概述与演进目标
- 技术栈架构
- 系统架构设计
- 硬件资源预算

### 2. [安全架构设计](./02-security-architecture.md)
- 安全架构设计
- 身份认证与访问控制
- 数据保护策略
- 安全监控与审计

### 3. [依赖版本管理系统](./03-dependency-management.md)
- 精确版本控制策略
- 依赖安全扫描
- 供应链安全验证
- 合规性检查

### 4. [开发规范与质量保证](./04-development-standards.md)
- 开发规范体系
- 代码质量保证
- CI/CD流水线
- 质量门禁机制

### 5. [API设计规范](./05-api-design.md)
- RESTful API设计原则
- OpenAPI 3.0规范
- 版本控制策略
- SDK示例

### 6. [技术实现细节](./06-technical-implementation.md)
- 核心组件实现
- 性能优化策略
- 内存管理机制
- 异常处理框架

### 7. [部署与监控](./07-deployment-monitoring.md)
- 部署策略
- 监控体系
- 运维自动化
- 健康检查机制

### 8. [风险管理](./08-risk-management.md)
- 风险识别与评估
- 缓解策略
- 应急响应预案
- 业务连续性保障

### 9. [项目管理与治理](./09-project-management.md)
- 项目治理结构
- 开发流程管理
- 变更控制机制
- 决策记录模板

### 10. [文档维护指南](./10-documentation-guide.md)
- 文档维护流程
- 版本控制规范
- 自动化文档生成
- 文档质量保证

## 快速导航

### 架构师关注
- [核心架构文档](./01-core-architecture.md) - 系统整体设计
- [技术实现细节](./06-technical-implementation.md) - 具体实现方案

### 安全专家关注
- [安全架构设计](./02-security-architecture.md) - 安全设计规范
- [依赖版本管理系统](./03-dependency-management.md) - 供应链安全

### 开发团队关注
- [开发规范与质量保证](./04-development-standards.md) - 开发标准
- [API设计规范](./05-api-design.md) - 接口规范

### Dev Agent开发标准 (BMad工作流专用)
- [编码标准](./coding-standards.md) - 代码格式和风格规范
- [技术栈配置](./tech-stack.md) - 技术选择和版本要求
- [项目结构规范](./source-tree.md) - 目录组织和文件命名

### DevOps团队关注
- [部署与监控](./07-deployment-monitoring.md) - 运维指南
- [风险管理](./08-risk-management.md) - 应急处理

### 项目管理关注
- [项目管理与治理](./09-project-management.md) - 管理流程
- [文档维护指南](./10-documentation-guide.md) - 文档规范

## 版本信息

- **文档版本**: v1.1
- **创建日期**: 2025-08-17
- **维护者**: Winston (Architect)
- **最后更新**: 2025-08-18 (添加Dev Agent专用开发标准文件)

## 相关文档

- [产品需求文档 (PRD)](../PRD/) - 业务需求与功能规格
- [API接口规范](../api_interface_specification.md) - 详细API文档
- [部署指南](../deployment_guide.md) - 部署操作手册