# 当前任务

## 状态

P4 MCP 规范合规修复已完成，待提交。

## P4 完成摘要

### P0 — MUST 级别
| ID | 修复内容 | 状态 |
|------|----------|------|
| P0-1 | get_process_tree 返回 None 时抛 ToolError | Done |
| P0-3 | FastMCP 声明 version="0.3.0" | Done |

### P1 — SHOULD 级别
| ID | 修复内容 | 状态 |
|------|----------|------|
| P1-1 | Resource not found 改用 ResourceError | Done |
| P1-3 | ping 重命名为 health_check | Done |
| P1-4 | registry.py 拆分为 registry.py + search.py（265+128 行） | Done |
| P1-5 | HTTP Origin 验证 (OPROCESS_ALLOWED_ORIGINS) | Done |

### P2 — 改进
| ID | 修复内容 | 状态 |
|------|----------|------|
| P2-1 | vector search N+1 → JOIN 批量查询 | Done |
| P2-2 | get_responsibilities 全层拉取 → get_children | Done |
| P2-3 | build_path_string → 批量缓存优化 | Done |
| P2-4 | Resource URI 参数正则校验 | Done |
| P2-5 | _to_json() 统一到 serialization.py | Done |
| P2-6 | session_id 完整 UUID4 | Done |
| P2-7 | audit session_id 格式校验 | Done |

## 验证结果
- ruff check: 零 error
- pytest: 201 passed
- 覆盖率: 90.55% (≥ 80%)
- 无文件超 300 行
