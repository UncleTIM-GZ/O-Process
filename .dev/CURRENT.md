# 当前任务

## 状态

P7 — SHOULD/MAY 合规 + P2/P3 打磨（已完成）。
计划文件: `docs/plans/2026-02-24-fix-p7-should-may-polish-plan.md`

## P7 修复清单

| ID | 修复内容 | 优先级 | 状态 |
|------|----------|--------|------|
| S10 | Tool title 字段（8 个） | SHOULD | Done |
| S11 | Prompt title 字段（3 个） | SHOULD | Done |
| P2-1 | CLAUDE.md 向量模型描述更新 | P2 | Done |
| P2-2 | 删除 get_recent_logs() 死代码 | P2 | Done |
| P3-1 | vector_search 双重调用修复 | P3 | Done |
| P3-2 | audit_log_enabled 配置生效 | P3 | Done |
| P3-4 | 空 resources/ 目录清理 | P3 | Done |

## 审查基线

- MUST 合规: 11/11 (100%)
- SHOULD 合规: 12/12 (100%)
- 覆盖率: 94.72%
- 规范版本: MCP Spec 2025-11-25

## 历史

### P6（已完成，commits cea0143 + a499cfa）
- P6-1~P6-4: P0 正确性修复（版本 + gateway + health_check + README）
- P6-5~P6-7: SHOULD 合规 + 测试覆盖率
- P6-8~P6-10: MCP Prompts + logging + atexit 线程安全

### P5（已完成，commits 23292d1 + 7d2c44a + 323d9b1）
- P5-1~P5-4: MCP error types + input validation + exception handling
- P5-5~P5-7: docstrings + rate limit config + health check vec
- P5 Commit 3: todo cleanup + plan files archive

### P4（已完成，commits b71497b + 07d12be）
- P0: ToolError guard + version 声明
- P1: ResourceError + health_check + registry 拆分 + Origin 验证
- P2: JOIN 优化 + UUID4 + 批量缓存 + serialization 统一
