# 实施计划

## Implementation Recommendations (Revised based on research)

### Progressive Implementation Path

**Phase 1: Robust Foundation** (3 months)
- Implement the self-developed DAG engine, keeping memory footprint under 50MB.
- Establish the feature flag and shadow-write validation mechanisms.
- Deploy traditional rule-based validation with 85-90% accuracy.
- Validate the practical feasibility of the memory budget table.

**Phase 2: Intelligent Enhancement** (2 months)
- Integrate UMI-OCR HTTP API, supporting dual-layer PDF generation.
- Deploy Qwen-7B-Chat-Int4, running within the 4GB memory limit.
- Implement hybrid intelligent validation, increasing accuracy to 95%+.
- Establish a complete performance monitoring system.

**Phase 3: Platform Finalization** (2 months)
- Develop a visual workflow editor.
- Establish standardized API interfaces and documentation.
- Finalize the auditing mechanism and version control.
- Perform performance optimization and user experience improvements.

### Success Criteria (Quantitative Metrics)

**Short-term Goals** (3 months):
- Successfully refactor `main.py` into a modular architecture.
- Node engine memory footprint < 50MB, task latency < 50ms.
- Rule-based validation improves data quality by over 15%.

**Mid-term Goals** (6 months):
- AI feature integration complete, with OCR recognition rate > 85% and LLM accuracy > 90%.
- Full API interface is live, supporting integration with external systems.
- Workflow configuration UI is user-friendly for non-technical users.

**Long-term Goals** (12 months):
- Become a benchmark auxiliary platform for the archive digitization industry.
- Achieve enterprise-level performance metrics under 8GB hardware constraints.
- Establish a replicable node-based architecture paradigm.

---

## Technical Feasibility Confirmation (Based on research)

Based on systematic online research and technical validation, the node-based architecture proposed in this PRD has **very high technical feasibility**:

✅ **Technology selections are thoroughly validated**: UMI-OCR, Qwen-7B, and the self-developed DAG engine all have successful precedents.
✅ **Hardware constraints can be precisely met**: The detailed memory budget ensures full utilization of 8GB of RAM.
✅ **Risk controls are comprehensive**: Feature flags, rollback mechanisms, and degradation strategies provide full coverage.
✅ **Performance metrics are realistic and achievable**: Based on actual research data, not estimations.

**It is recommended to start development immediately**, focusing on infrastructure construction and implementing safe migration mechanisms.

---

## Revision Comparison Table (v2.1-freeze)

| Revised Item | Original Version Content | After Redline Revision | Reason for Revision |
|---|---|---|---|
| AI Concurrency Limit | "AI node concurrency ≤1, supports queueing" | "AI node concurrency ≤1 (Hard Limit): When queuing/backpressure is triggered, GUI input echo < 200ms" | Unify terminology, remove legacy "≤4" references. |
| Non-AI Performance Baseline| "1000 records ≤ 10s" | "1000 records ≤ 3s (P95), Pillow baseline" | Set current performance as a hard baseline to prevent regression. |
| Memory Redline | "Total 7994MB, 198MB headroom" | "Total 7704MB ≤ 6.5GB, reserving ≥ 20% headroom" | Increased safety margin to avoid resource contention. |
| LLM Strategy | "Qwen-7B-Chat-Int4 is resident" | "Hunyuan-1.8B/4B(INT4) resident, 7B loaded on-demand" | Two-tier strategy to avoid resource contention. |
| OCR Architecture | "UMI-OCR + PaddleOCR as backup" | "Dual-channel: UMI-OCR/Embedded PaddleOCR, advanced channel: dots.ocr" | Dual-channel design with clear trigger conditions. |
| SQLite Configuration | "WAL + NORMAL + cache_size" | "WAL + NORMAL + busy_timeout=5000 + short transactions <50ms" | Detailed operational guidelines to prevent GUI freezes. |
| Audit Mechanism | "Event logging format" | "Anti-tampering via event hash chain + daily root hash signature + retention ≥3 years" | Strengthened anti-tampering capabilities. |
| Migration Strategy | "Feature flag migration strategy" | "Canary release via feature_flags + shadow write + 4-step rollback SOP" | Actionable standard operating procedure. |
| Acceptance Criteria| "Workflow support: AI concurrency ≤1" | "AI node concurrency ≤1 (Hard Limit) + backpressure drill passed" | Quantifiable and testable metrics. |
| Config Management | "dynaconf + cerberus" | "Use existing ConfigManager + JSON Schema to avoid dual systems" | Maintain consistency in the technology stack. |

---

*This PRD document version: 2.1-freeze (Redline Revision Frozen Version)*
*Last Updated: 2025-08-17*
*Document Status: 10 redline revisions based on GPT-5 secondary review, ready for Epic/Story design phase.*
*Main Revisions: AI concurrency hard limit, performance hard baseline, memory redline, two-tier LLM strategy, SQLite operational guidelines, anti-tampering audit.*
