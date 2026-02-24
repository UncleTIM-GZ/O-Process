# O'Process MCP Server — 产品经理视角：业务逻辑文档

> **版本**: 0.3.0 | **最后更新**: 2026-02-25 | **数据来源**: 源码实际实现

---

## 1. 产品定位

O'Process 是一个 **AI 原生流程分类知识服务器**，基于 MCP（Model Context Protocol）协议对外提供服务。

**核心价值主张**：将企业流程分类框架（2325 个流程节点 + 3910 个 KPI 指标）通过标准化 MCP 协议暴露给 AI 客户端，使 LLM 能够进行流程查询、岗位映射、KPI 分析和职责文档生成。

**定位**：流程知识 MCP Server，不是 Agent 治理平台。核心能力 = 查询 + 映射 + 生成。

---

## 2. 数据资产

### 2.1 流程节点（processes 表）

| 属性 | 说明 |
|------|------|
| **总量** | 2325 个流程节点 |
| **来源** | APQC PCF 7.4（1921 条）+ ITIL 4（141 条）+ SCOR 12.0（164 条）+ AI-era（99 条） |
| **层级** | 5 级树形结构（L1-L5） |
| **L1 分类** | 13 个顶层分类（ID: 1.0 ~ 13.0） |
| **领域（domain）** | Operating / Management / AI-era |
| **双语** | 每个节点包含 name_zh / name_en / description_zh / description_en |
| **标签系统** | tags（JSON 数组）、source（来源标注）、kpi_refs（KPI 关联） |
| **AI 上下文** | ai_context 字段：为 LLM 提供流程语义理解辅助文本 |

### 2.2 KPI 指标（kpis 表）

| 属性 | 说明 |
|------|------|
| **总量** | 3910 个 KPI 条目 |
| **关联** | 每个 KPI 通过 process_id 关联到具体流程节点 |
| **字段** | name_zh / name_en / unit（单位）/ formula（公式）/ category（分类）/ direction（方向）/ scor_attribute |

### 2.3 向量嵌入（process_embeddings 表 + vec_processes 虚拟表）

| 属性 | 说明 |
|------|------|
| **模型** | gemini-embedding-001 |
| **维度** | 768 维 |
| **用途** | 语义搜索：将用户自然语言查询与流程节点进行余弦相似度匹配 |
| **回退** | 当向量搜索不可用时，自动降级为 SQL LIKE 文本匹配 |

### 2.4 角色映射（role_mappings 表）

- 当前状态：表已创建，预留为未来缓存层
- 实际岗位→流程映射通过实时语义搜索完成

---

## 3. 功能清单

### 3.1 MCP Tools（8 个）

| # | Tool 名称 | 功能描述 | 输入参数 | 输出 |
|---|-----------|---------|---------|------|
| 1 | `search_process` | 语义搜索流程节点 | query, lang, limit, level | 匹配列表 + 相似度分数 |
| 2 | `get_process_tree` | 获取流程子树（层级结构） | process_id, max_depth(1-5) | 嵌套 JSON 树 |
| 3 | `get_kpi_suggestions` | 获取流程 KPI 指标建议 | process_id | KPI 列表 + 计数 |
| 4 | `compare_processes` | 对比多个流程节点差异 | process_ids（逗号分隔） | 属性对比矩阵 |
| 5 | `get_responsibilities` | 生成岗位职责描述 | process_id, lang, output_format | JSON 或 Markdown |
| 6 | `export_responsibility_doc` | 导出完整岗位说明书 | process_ids, lang, role_name | Markdown + 溯源附录 |
| 7 | `map_role_to_processes` | 岗位→流程映射 | role_description, lang, limit, industry | 带置信度的流程列表 |
| 8 | `health_check` | 健康检查 | 无 | 状态 + 统计数据 |

**关键业务规则**：
- 所有 Tool 返回统一信封格式：`{ result, provenance_chain, session_id, response_ms }`
- 搜索类 Tool（search_process、map_role_to_processes）在低置信度时触发 **BoundaryResponse**（阈值 0.45）
- 所有 Tool 调用经过 Gateway 统一路由，自动计时和审计

### 3.2 MCP Resources（6 个）

| URI 模式 | 功能 | MIME 类型 |
|----------|------|-----------|
| `oprocess://process/{id}` | 获取单个流程节点完整信息 | application/json |
| `oprocess://category/list` | 获取 13 个 L1 分类列表 | application/json |
| `oprocess://role/{role_name}` | 通过语义搜索获取角色流程映射 | application/json |
| `oprocess://audit/session/{session_id}` | 获取会话审计日志 | application/json |
| `oprocess://schema/sqlite` | 获取数据库 DDL 定义 | text/plain |
| `oprocess://stats` | 获取框架统计数据 | application/json |

### 3.3 MCP Prompts（3 个）

| Prompt 名称 | 标题 | 功能 |
|-------------|------|------|
| `analyze_process` | Process Analysis Workflow | 引导 LLM 完成流程分析（tree + KPI → 报告） |
| `generate_job_description` | Job Description Generator | 引导生成岗位说明书（responsibilities + export） |
| `kpi_review` | KPI Review Workflow | 引导 KPI 审查（获取 → 评估 → 建议） |

每个 Prompt 支持 zh/en 双语，包含参数验证（process_id 格式、lang 范围、role_name 安全过滤）。

---

## 4. 治理能力（Governance-Lite）

三项透明增强能力，不影响主流程：

### 4.1 SessionAuditLog（会话审计日志）

- **类型**：Append-Only（追加写入）
- **保护**：数据库触发器禁止 UPDATE 和 DELETE
- **字段**：session_id / tool_name / input_hash(SHA256) / output_node_ids / lang / response_ms / timestamp / governance_ext / request_id
- **幂等性**：request_id 唯一索引，重复请求静默忽略
- **可靠性**：写入失败不阻塞主流程（try/except + warning）

### 4.2 BoundaryResponse（边界响应）

- **触发条件**：向量搜索最佳匹配分数 < 0.45（可配置）
- **行为**：不直接拒绝，而是返回结构化降级响应
- **响应内容**：boundary_triggered / best_score / threshold / suggestion（中文建议） / nearest_valid_nodes（最近 3 个节点）
- **仅适用于**：有 score 的向量搜索结果；LIKE 回退模式跳过

### 4.3 ProvenanceChain（溯源链）

- **目的**：追踪每个 Tool 响应的数据推导路径
- **结构**：node_id / name / confidence(0.0-1.0) / path(祖先路径) / derivation_rule
- **规则类型**：`semantic_match`（搜索匹配）/ `rule_based`（层级遍历）/ `direct_lookup`（精确查找）
- **批量优化**：路径构建使用 `build_path_strings_batch` 消除 N+1 查询

---

## 5. 用户场景

### 场景 1：流程探索

```
用户意图: "了解财务管理流程的完整结构"
→ Prompt: analyze_process(process_id="8.0")
→ Tool 调用链: get_process_tree("8.0") → get_kpi_suggestions("8.0") → 分析报告
```

### 场景 2：岗位职责生成

```
用户意图: "为 IT 运维经理生成岗位说明书"
→ Prompt: generate_job_description(process_ids="8.1,8.2", role_name="IT运维经理")
→ Tool 调用链: get_responsibilities → export_responsibility_doc → Markdown 文档
```

### 场景 3：KPI 审查

```
用户意图: "审查供应链管理流程的 KPI 指标"
→ Prompt: kpi_review(process_id="4.0")
→ Tool 调用链: get_kpi_suggestions("4.0") → 审查建议
```

### 场景 4：岗位映射

```
用户意图: "这个岗位描述对应哪些流程？"
→ Tool: map_role_to_processes(role_description="负责IT基础设施运维...")
→ 返回: 带置信度评分的流程列表 + BoundaryResponse（如置信度低）
```

---

## 6. 双语支持

| 层面 | 中文 (zh) | 英文 (en) |
|------|-----------|-----------|
| 流程名称 | name_zh | name_en |
| 流程描述 | description_zh | description_en |
| KPI 名称 | name_zh | name_en |
| Prompt 模板 | 中文引导文本 | 英文引导文本 |
| Boundary 建议 | 中文建议文本 | — (当前仅中文) |

- 默认语言：zh（通过 `[tool.oprocess].default_language` 配置）
- 所有 Tool 的 `lang` 参数严格校验，仅接受 "zh" 或 "en"

---

## 7. 质量指标

| 指标 | 门禁值 | 当前值 |
|------|--------|--------|
| 测试覆盖率 | >= 80% | 94.75% |
| Ruff Lint | 0 errors | 0 errors |
| 测试用例 | — | 262 passed |
| 文件行数限制 | <= 300 行 | 最大 259 行 |
| 函数行数限制 | <= 50 行 | 符合 |

---

## 8. 配置项

通过 `pyproject.toml` 的 `[tool.oprocess]` 节配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `boundary_threshold` | 0.45 | BoundaryResponse 触发阈值 |
| `audit_log_enabled` | true | 是否启用审计日志 |
| `default_language` | "zh" | 默认语言 |
| `rate_limit_max_calls` | 60 | 速率限制：窗口内最大调用次数 |
| `rate_limit_window_seconds` | 60 | 速率限制：时间窗口（秒） |

---

## 9. 传输协议

| 模式 | 命令 | 认证 | 适用场景 |
|------|------|------|---------|
| stdio | `python -m oprocess` | 无需 | Claude Desktop、CLI 集成 |
| SSE | `--transport sse --port 8000` | Bearer Token | Web 客户端 |
| streamable-http | `--transport streamable-http` | Bearer Token | HTTP 流式客户端 |

HTTP 模式需设置环境变量 `OPROCESS_API_KEY`，可选 `OPROCESS_ALLOWED_ORIGINS` 控制 CORS。
