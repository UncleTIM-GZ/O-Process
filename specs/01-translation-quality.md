# Spec 01: 高质量中文翻译

## 1. 概述

### 功能目标

将 O'Process 框架的 2325 个流程节点和 3910 个 KPI 指标从英文翻译为高质量中文，使双语数据达到 AI Agent 生产可用级别。

### 用户价值

- 中文用户可通过中文查询获得精准的流程匹配结果
- AI Agent 的语义搜索在中文场景下召回率显著提升
- `framework-zh.json` 可直接用于中文 UI 展示

### 范围边界

**做什么**:
- 使用 Anthropic API 翻译所有节点 name.zh 和 description.zh
- 翻译所有 KPI 的 name.zh
- 修复 ai_context 字段的 200 字符截断问题（改为句子边界截断）
- 保留词汇表作为术语一致性保障层

**不做什么**:
- 不翻译 ai_context 为中文（v2 双语嵌入方案）
- 不填充五柱字段（v2 范围）
- 不修改 schema.json 结构

## 2. 详细需求

### 2.1 功能需求

| 编号 | 需求 | 优先级 |
|------|------|--------|
| FR-001 | 所有 2325 个节点的 name.zh 为纯中文 | P0 |
| FR-002 | 所有 2325 个节点的 description.zh 为流畅中文 | P0 |
| FR-003 | 所有 3910 个 KPI 的 name.zh 为中文 | P0 |
| FR-004 | ai_context 按句子边界截断（不超过 300 字符） | P0 |
| FR-005 | 翻译保持专业术语一致性（使用术语表约束） | P1 |
| FR-006 | 无 API Key 时降级为改进版词汇表翻译 | P1 |
| FR-007 | 翻译结果可缓存，避免重复调用 API | P2 |

### 2.2 非功能需求

- **成本**: Batch API 翻译 ~8500 条文本，预估 < $5 USD
- **性能**: API 翻译不在实时管道中，作为独立预处理步骤
- **幂等性**: 重复运行不重新翻译已有高质量翻译的条目

## 3. 技术设计

### 3.1 翻译策略

```
translate_api.py (独立脚本，需 ANTHROPIC_API_KEY)
  ├── 读取 framework.json → 提取需翻译文本
  ├── 读取 kpis.json → 提取 KPI 名称
  ├── 批量调用 Anthropic Messages API
  ├── 应用术语表后处理（一致性校正）
  ├── 写回 framework.json 和 kpis.json
  └── 生成翻译缓存 (.dev/translation-cache.json)

translate.py (管道内翻译，词汇表兜底)
  └── 仅处理 API 未覆盖的条目
```

### 3.2 API 调用设计

每批 20 条文本，使用系统提示约束翻译风格：

```
System: 你是企业流程管理领域的专业翻译。将英文流程名称和描述翻译为简洁准确的中文。
        使用以下术语表保持一致: {glossary}
        只输出翻译结果的 JSON，不要解释。

User: {"items": [
  {"id": "1.1.1", "field": "name", "en": "Analyze the External Environment"},
  {"id": "1.1.1", "field": "description", "en": "Determine the..."},
  ...
]}
```

### 3.3 ai_context 修复

在 `parse_pcf.py` 中将 `description[:200]` 改为句子边界截断：

```python
def _truncate_at_sentence(text: str, max_len: int = 300) -> str:
    if len(text) <= max_len:
        return text
    # 找最近的句号
    truncated = text[:max_len]
    last_period = max(truncated.rfind('.'), truncated.rfind('。'))
    if last_period > max_len // 2:
        return truncated[:last_period + 1]
    return truncated
```

## 4. 开发检查点

- [ ] CP1: 创建 `scripts/translate_api.py` — API 翻译脚本
- [ ] CP2: 修复 `scripts/parse_pcf.py` 中 ai_context 截断逻辑
- [ ] CP3: 更新 `scripts/translate.py` 兼容 API 翻译缓存
- [ ] CP4: 更新 `scripts/run_pipeline.py` 集成新流程
- [ ] CP5: 运行管道，验证质量门禁全部通过
- [ ] CP6: 生成翻译质量报告（纯中文比例、混合比例）

## 5. 测试要点

- API 翻译脚本在有/无 API Key 时的行为
- 翻译缓存的读取和写入
- ai_context 截断在各种长度下的行为
- 管道完整运行后 9 项质量门禁全通过
- 翻译后 name.zh 纯中文比例 > 95%

## 6. 验收标准

- [ ] name.zh 纯中文节点比例 > 95%（当前 2%）
- [ ] description.zh 非英文副本比例 > 90%（当前 61%）
- [ ] KPI name.zh 非空比例 = 100%（当前 0%）
- [ ] ai_context 截断在句子边界比例 > 90%
- [ ] 9 项质量门禁全部通过
- [ ] 翻译缓存文件可复用
