# 当前任务

## 状态

P6 — MCP Spec 2025-11-25 全面合规审查修复（待开始）。
计划文件: `docs/plans/2026-02-24-fix-p6-mcp-spec-2025-11-25-audit-plan.md`

## P6 修复清单

| ID | 修复内容 | 优先级 | 状态 |
|------|----------|--------|------|
| P6-1 | 版本号统一 0.3.0 | P0 | Done |
| P6-2 | Gateway 单例统一 (消除双 session_id) | P0 | Done |
| P6-3 | health_check 走 Gateway | P0 | Done |
| P6-4 | README 同步更新 | P0 | Done |
| P6-5 | destructiveHint=False 显式声明 | P1 | Done |
| P6-6 | resources.py 测试覆盖率 → 80%+ | P1 | Done |
| P6-7 | auth.py 测试覆盖率 → 80%+ | P1 | Done |
| P6-8 | MCP Prompts (3 个引导模板) | P2 | Done |
| P6-9 | MCP logging capability | P2 | Done |
| P6-10 | atexit 线程安全修复 | P2 | Done |

## 审查基线

- MUST 合规: 16/16 (100%)
- SHOULD 合规: ~85%
- 覆盖率: 94.50%
- 规范版本: MCP Spec 2025-11-25

## 历史

### P5（已完成，commits 23292d1 + 7d2c44a + 323d9b1）
- P5-1~P5-4: MCP error types + input validation + exception handling
- P5-5~P5-7: docstrings + rate limit config + health check vec
- P5 Commit 3: todo cleanup + plan files archive

### P4（已完成，commits b71497b + 07d12be）
- P0: ToolError guard + version 声明
- P1: ResourceError + health_check + registry 拆分 + Origin 验证
- P2: JOIN 优化 + UUID4 + 批量缓存 + serialization 统一
