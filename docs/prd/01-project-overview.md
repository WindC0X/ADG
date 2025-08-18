# 项目概述

## Document Revision History

**Revision Version**: v2.1-freeze
**Revision Date**: 2025-08-17
**Reason for Revision**: Redline revisions based on the GPT-5-thinking secondary review report; version frozen.

**Main Revisions**:
- Unified AI concurrency limit to ≤1 (hard limit).
- Set a hard performance baseline for non-AI tasks (Pillow: 1000 entries ≤3s).
- Adjusted the memory redline to ≤6.5GB (20% headroom).
- Updated the two-tier LLM strategy and dual-channel OCR design.
- Reinforced SQLite/WAL operational guidelines and the anti-tampering audit mechanism.

---

# Project Analysis and Context

### Existing Project Overview

**Analysis Source**: Existing brownfield architecture documentation in the IDE (docs/brownfield-architecture.md).

**Current Project Status**: 
ADG (Archive Directory Generator) is a mature Tkinter desktop application specialized in generating various types of archive directory Excel files. The project's core feature is its support for three row-height calculation schemes, ensuring precise layout for Excel printing.

### Analysis of Available Documentation

✅ **Technology Stack Documentation** - Fully documented via the brownfield architecture document.
✅ **Source Code Architecture** - Detailed module structure and responsibility division.
✅ **Coding Standards** - Partially documented in project documents.
✅ **API Documentation** - Core module interfaces are documented.
✅ **External API Documentation** - Windows GDI/COM integration is documented.
✅ **Technical Debt Documentation** - Comprehensive analysis of technical debt and constraints.

### Definition of Enhancement Scope

**Enhancement Type**: ✅ **Project Refactoring** - Comprehensive improvements across multiple aspects.

**Enhancement Description**: 
Systematically refactor the ADG to transform it from a specialized tool into an auxiliary platform for the entire archive digitization workflow.

**Archive Digitization Process**: 
Receive archives (record count) → Organize and classify archives → Write page numbers/codes → Enter directory data → Check and verify directory data, import into processing system → Scan archives → Convert images (dual-layer PDF) → Re-verify directory data → Convert and print directories → Bind into volumes → Organize and hand over digital data.

**Impact Assessment**: ✅ **Major Impact** - Requires architectural-level refactoring and changes.

### Goals and Background Context

**Goals**:
• Expand ADG from a single directory conversion tool to a full-chain auxiliary platform for the archive digitization process.
• Provide intelligent assistance across 11 stages of the archive process, particularly those related to directories.
• Enhance archive management efficiency and quality through LLMs and automation.
• Establish a progressive technology upgrade path, transitioning smoothly from rule-driven to AI-driven.
• Achieve optimal performance under the hardware constraints of an i5-9400 CPU + 8GB RAM.

**Background Context**:
The project currently specializes in the "Convert and print directories" stage. After refactoring, it will serve multiple stages, including "Enter directory data," "Check and verify directory data," and "Re-verify directory data." A progressive upgrade strategy will be adopted, using an atomic node architecture to enable flexible workflow configuration, ultimately establishing a complete archive directory lifecycle management capability.

**Changelog**:
| Change | Date | Version | Description | Author |
|---|---|---|---|---|
| Refactoring PRD Kickoff | 2025-08-17 | 2.0-dev | Initiated planning for systematic refactoring. | Product Manager |
| Key Revisions | 2025-08-17 | 2.1-dev | Significant revisions based on review reports and research. | Product Manager |

