---
review_agents: [kieran-python-reviewer, code-simplicity-reviewer, security-sentinel, performance-oracle]
plan_review_agents: [kieran-python-reviewer, code-simplicity-reviewer]
---

# Review Context

O'Process 是一个 Python MCP Server（FastMCP），为 AI Agent 提供企业流程知识查询能力。

## 技术栈
- Python + FastMCP + SQLite + sqlite-vec
- 测试：pytest + pytest-benchmark
- Lint：Ruff
- 打包：uv + pyproject.toml

## 架构要点
- 所有 Tool 必须通过 `ToolGatewayInterface` 执行，禁止直接调用
- 所有 Tool 响应封装为 `ToolResponse`（result / provenance_chain / session_id / response_ms）
- Governance-Lite 三能力：SessionAuditLog（追加写入）、BoundaryResponse（阈值触发）、ProvenanceChain（溯源链）
- SessionAuditLog 写入失败不得阻塞主流程
- BoundaryResponse 阈值从配置读取，禁止硬编码

## 代码约束
- 单文件 ≤ 300 行，单函数 ≤ 50 行，嵌套 ≤ 3 层
- 所有 public function 必须有类型注解
- SQL 必须使用参数化查询，禁止字符串拼接
- async def 用于所有 Tool handler 和 gateway 方法

## 安全关注
- input_hash 使用 SHA256 前 16 位，禁止存储原始输入
- oprocess_content.xlsx 不得进入 repo
- 审计日志表有 INSERT-ONLY 触发器，禁止 UPDATE/DELETE

## 性能目标
- P50 < 100ms / P95 < 300ms（本地 stdio）
- ProvenanceChain 增量开销 < 20ms
- SessionAuditLog 写入 < 5ms
- 内存 < 150MB

## 数据完整性
- SQLite 审计日志表有防写触发器
- processes 表的 embedding 字段为 BLOB（1536 维 float32）
- 所有流程节点双语（zh + en）
