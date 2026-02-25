# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 产品定位

O'Process 是流程知识 MCP Server，不是 Agent 治理平台。
核心能力：查询 · 映射 · 生成。Governance-Lite 是透明增强层。

## 技术栈

- **语言**: Python
- **MCP 框架**: FastMCP
- **数据存储**: SQLite + sqlite-vec（向量搜索）
- **向量模型**: gemini-embedding-001（768 维，离线预计算）
- **测试**: pytest + pytest-benchmark
- **Lint**: Ruff
- **打包**: uv + pyproject.toml

## 常用命令

```bash
# 安装依赖
uv sync

# 运行 MCP Server（stdio 模式）
uv run python -m oprocess.server

# Lint
ruff check .

# 测试
pytest
pytest tests/test_tools/              # 单个测试目录
pytest tests/test_governance/test_audit.py  # 单个测试文件
pytest -k "test_search"               # 按名称匹配
pytest --benchmark-only               # 仅性能测试

# 提交前完整检查
ruff check . && pytest && pytest --benchmark-only

# 数据脚本
python scripts/ingest.py              # Excel → SQLite
python scripts/embed.py               # 批量 embedding
python scripts/translate.py           # 多语言翻译
```

## 开发顺序

M0（数据入库）→ M1（Server + Gateway）→ M2（7 Tool + Gov-Lite）→ M3（集成发布）

Claude Code 从 M0 开始介入。M-1 为 Tim O 内容创作阶段。

## 核心规范

- 所有 Tool 签名严格遵循 PRD 第 4 节（`OProcess-PRD-v2.0.docx`）
- 所有 Tool 响应封装为 `ToolResponse`（result / provenance_chain / session_id / response_ms）
- Tool 逻辑必须通过 `ToolGatewayInterface` 执行，不直接调用
- `SessionAuditLog` 写入失败不得影响主流程
- `BoundaryResponse` 阈值从配置读取（pyproject.toml），不硬编码
- 内容文件（oprocess_content.xlsx）不进 Repo

## 7 个 MCP Tools

| Tool | 功能 | 溯源输出 |
|------|------|----------|
| `search_process` | 语义搜索流程，低置信度返回 BoundaryResponse | 匹配节点路径 |
| `get_process_tree` | 返回分类节点子树（4 级层级） | — |
| `get_responsibilities` | 生成岗位职责描述 | 推导节点集 |
| `map_role_to_processes` | 岗位→流程列表（含置信度） | 置信度链 |
| `get_kpi_suggestions` | 流程节点 KPI 建议 | 节点来源 |
| `compare_processes` | 对比流程节点差异 | — |
| `export_responsibility_doc` | 生成完整岗位说明书（Markdown + 溯源附录） | 完整溯源图 |

## Governance-Lite 三能力（实现顺序）

1. **SessionAuditLog** — 追加写入型日志（最简单，先做）
2. **BoundaryResponse** — 向量距离 > 0.45 时结构化降级返回（搜索层改造）
3. **ProvenanceChain** — 每个 Tool 响应附加推导链（最复杂，最后做）

## 项目结构

```
src/oprocess/
├── server.py              # FastMCP 主入口
├── gateway.py             # ToolGatewayInterface + PassthroughGateway
├── tools/                 # 7 个 Tool 实现
├── governance/            # Gov-Lite 三能力
│   ├── provenance.py
│   ├── audit.py
│   └── boundary.py
└── db/                    # SQLite 连接与查询
scripts/                   # 数据处理脚本（ingest/embed/translate）
tests/
├── test_tools/
├── test_governance/
├── test_performance.py
└── fixtures/              # 标注测试集
```

## 质量门禁

- Ruff lint 零 error
- 类型注解覆盖所有 public function
- 测试覆盖率 ≥ 80%
- 语义搜索 Top-3 准确率 ≥ 85%（50 个标注查询集）
- P50 < 100ms / P95 < 300ms（本地 stdio）

## Code Constraints

- 单文件 ≤ 300 行，单函数 ≤ 50 行，嵌套 ≤ 3 层
- 重复代码 > 10 行必须抽象
- 每次改动 < 100 行，可测试增量
- 早返回 / guard clause 优先
- 组合优于继承

## Git Conventions

- **Main branch**: `main`
- **Branch naming**: `feature/<name>`, `fix/<name>`, `docs/<name>`
- Conventional commit: `feat(tools): add search_process`

