# AI Agent 可借鑑架構模式

> ⚠️ **定位說明**: 本文檔整理 Dexter 專案的設計模式，僅作為 **部分參考**。
> ArkScope 的完整架構設計請參閱 [LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md](./LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md) §1.3。
>
> **適用範圍**:
> - ✅ Agent 核心邏輯實現
> - ✅ Scratchpad 記錄機制
> - ✅ 工具管理模式
> - ✅ 上下文窗口管理 (Token Budget / Context Clearing)
> - ✅ 工具調用控制策略 (Graceful Exit)
> - ✅ Plugin 式工作流擴展 (Skills)
> - ✅ Subagent 模式 (LLM 路由器分派子工具)
> - ✅ API 快取策略 (Repository-Layer Cache)
> - ✅ Provider 級成本優化 (Prompt Caching)
> - ✅ Provider Registry (集中式 Provider 元數據)
> - ✅ Channel Plugin (Gateway 頻道抽象)
> - ✅ 安全內容包裝 (外部內容邊界防護)
> - ✅ Agent 分解模式 (職責拆分)
> - ✅ Sandbox 模式 (文件系統安全邊界)
> - ✅ Tool Approval 模式 (敏感工具審批)
> - ✅ Controller Pattern (Observer 模式狀態管理)
> - ❌ 監控系統設計 (Dexter 沒有此概念)
> - ❌ 持續狀態管理 (Dexter 是無狀態的)
> - ❌ 程式碼動態生成執行 (Dexter 不支援)

本文檔總結 Dexter 專案中值得借鑑的架構模式，適用於構建 Agent 核心功能。

---

## 目錄

1. [Agent Loop 模式](#1-agent-loop-模式)
2. [Scratchpad 模式](#2-scratchpad-模式-jsonl-追加式上下文)
3. [Context Compaction 模式](#3-context-compaction-模式) *(已被 #10 Context Clearing 取代)*
4. [Tool Registry 模式](#4-tool-registry-模式)
5. [Lazy Initialization 模式](#5-lazy-initialization-模式)
6. [Event-driven UI 模式](#6-event-driven-ui-模式-asyncgenerator)
7. [Token Budget 模式](#7-token-budget-模式-llm-上下文選擇)
8. [Graceful Exit 模式](#8-graceful-exit-模式-軟引導式工具限制)
9. [Skills System 模式](#9-skills-system-模式-plugin-式工作流)
10. [Context Clearing 模式](#10-context-clearing-模式-取代摘要迭代) *(取代 #3)*
11. [Subagent 模式](#11-subagent-模式-llm-路由器)
12. [Repository-Layer Cache 模式](#12-repository-layer-cache-模式)
13. [Prompt Caching 模式](#13-prompt-caching-模式-provider-level)
14. [Provider Registry 模式](#14-provider-registry-模式-集中式-provider-元數據)
15. [Channel Plugin 模式](#15-channel-plugin-模式-gateway-頻道抽象)
16. [安全內容包裝模式](#16-安全內容包裝模式-外部內容邊界防護)
17. [Agent 分解模式](#17-agent-分解模式-職責拆分)
18. [Sandbox 模式](#18-sandbox-模式-文件系統安全邊界)
19. [Tool Approval 模式](#19-tool-approval-模式-敏感工具審批)
20. [Controller Pattern](#20-controller-pattern-observer-模式狀態管理)

---

## 1. Agent Loop 模式

### 概念

簡化的 AI Agent 執行循環，讓 LLM 自行決定何時需要工具、何時可以回答：

```
用戶查詢 → [Agent Loop] → 最終答案
              ↓
      while (iteration < max) {
        1. 調用 LLM (帶工具綁定)
        2. 如果無工具調用 → 生成最終答案
        3. 執行工具，記錄結果
        4. 構建下一輪 prompt
      }
```

### 實現示例

```typescript
// src/agent/agent.ts
export class Agent {
  async *run(query: string): AsyncGenerator<AgentEvent> {
    const scratchpad = new Scratchpad(query);
    let currentPrompt = query;
    let iteration = 0;

    while (iteration < this.maxIterations) {
      iteration++;

      // 調用 LLM (帶工具綁定)
      const response = await this.callModel(currentPrompt);

      // 沒有工具調用 = 準備生成最終答案
      if (!hasToolCalls(response)) {
        const fullContext = scratchpad.getFullContexts();
        const answer = await this.generateFinalAnswer(query, fullContext);
        yield { type: 'done', answer, iterations: iteration };
        return;
      }

      // 執行工具，記錄到 Scratchpad
      for (const toolCall of response.tool_calls) {
        const result = await this.executeTool(toolCall);
        const summary = await this.summarizeResult(toolCall, result);
        scratchpad.addToolResult(toolCall.name, toolCall.args, result, summary);
        yield { type: 'tool_end', tool: toolCall.name, result };
      }

      // 用摘要構建下一輪 prompt (Context Compaction)
      currentPrompt = buildIterationPrompt(query, scratchpad.getToolSummaries());
    }
  }
}
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **簡化架構** | 不需要分離的理解、規劃、執行階段 |
| **靈活應對** | LLM 自行決定需要多少輪工具調用 |
| **易於維護** | 單一循環邏輯，減少代碼複雜度 |
| **自然迭代** | 支持多輪工具調用和中間推理 |

### 適用場景

- 工具數量較少（< 10 個）的 Agent
- 查詢複雜度差異大的場景
- 希望快速迭代的原型開發

---

## 2. Scratchpad 模式 (JSONL 追加式上下文)

### 概念

使用 **JSONL (JSON Lines)** 格式的追加式日誌記錄 Agent 的所有工作：

```
.dexter/scratchpad/
└── 2026-01-21-153045_abc123def456.jsonl

# 每行一個 JSON 對象
{"type":"init","content":"What is Apple's revenue?","timestamp":"..."}
{"type":"tool_result","toolName":"financial_search",...,"llmSummary":"..."}
{"type":"thinking","content":"I have the data now","timestamp":"..."}
```

### 實現示例

```typescript
// src/agent/scratchpad.ts
interface ScratchpadEntry {
  type: 'init' | 'tool_result' | 'thinking';
  timestamp: string;
  content?: string;           // init/thinking
  toolName?: string;          // tool_result
  args?: Record<string, unknown>;
  result?: unknown;           // 完整結果
  llmSummary?: string;        // LLM 摘要
}

export class Scratchpad {
  private readonly filepath: string;

  constructor(query: string) {
    const hash = createHash('md5').update(query).digest('hex').slice(0, 12);
    const timestamp = new Date().toISOString().slice(0, 19).replace('T', '-').replace(/:/g, '');
    this.filepath = join('.dexter/scratchpad', `${timestamp}_${hash}.jsonl`);

    // 記錄初始查詢
    this.append({ type: 'init', content: query, timestamp: new Date().toISOString() });
  }

  addToolResult(toolName: string, args: Record<string, unknown>, result: string, llmSummary: string): void {
    this.append({
      type: 'tool_result',
      timestamp: new Date().toISOString(),
      toolName,
      args,
      result: this.parseResultSafely(result),
      llmSummary,
    });
  }

  // 追加式寫入 (JSONL 格式)
  private append(entry: ScratchpadEntry): void {
    appendFileSync(this.filepath, JSON.stringify(entry) + '\n');
  }

  // 讀取所有條目
  private readEntries(): ScratchpadEntry[] {
    return readFileSync(this.filepath, 'utf-8')
      .split('\n')
      .filter(line => line.trim())
      .map(line => JSON.parse(line));
  }
}
```

### JSONL 格式優勢

| 優勢 | 說明 |
|------|------|
| **追加友好** | 每行獨立，直接追加不需重寫整個文件 |
| **崩潰安全** | 部分寫入不會破壞整個文件 |
| **人類可讀** | 每行獨立 JSON，易於調試 |
| **流式處理** | 可逐行讀取，無需載入整個文件 |
| **版本友好** | 新增字段不影響舊條目解析 |

### 適用場景

- 需要持久化記錄的 Agent 工作日誌
- 需要崩潰恢復能力的長時間運行任務
- 需要事後分析和調試的場景

---

## 3. Context Compaction 模式

### 概念

在 Agent 迭代過程中，使用 **LLM 摘要** 代替完整數據構建 prompt，節省 token；在生成最終答案時，使用 **完整數據** 確保準確性：

```
迭代 1: 執行工具 A → 生成 LLM 摘要 A' → 存儲 (A, A')
迭代 2: 執行工具 B → 生成 LLM 摘要 B' → 存儲 (B, B')
        ↓
下一輪 prompt 使用 [A', B'] (摘要)
        ↓
最終答案 prompt 使用 [A, B] (完整數據)
```

### 實現示例

```typescript
// 工具執行後
const result = await tool.invoke(args);
const summary = await this.summarizeToolResult(query, toolName, args, result);
scratchpad.addToolResult(toolName, args, result, summary);

// 下一輪迭代 - 使用摘要
const summaries = scratchpad.getToolSummaries();
const iterationPrompt = `
Query: ${query}

Data gathered so far:
${summaries.map((s, i) => `${i + 1}. ${s}`).join('\n')}

Continue gathering data or provide final answer.
`;

// 最終答案 - 使用完整數據
const fullContexts = scratchpad.getFullContexts();
const finalPrompt = `
Query: ${query}

Complete data:
${fullContexts.map(ctx => `### ${ctx.toolName}\n${JSON.stringify(ctx.result, null, 2)}`).join('\n\n')}

Provide comprehensive answer based on the data above.
`;
```

### 摘要生成

```typescript
private async summarizeToolResult(
  query: string,
  toolName: string,
  args: Record<string, unknown>,
  result: string
): Promise<string> {
  const prompt = `
Summarize this tool result in relation to the user's query.

Query: ${query}
Tool: ${toolName}
Args: ${JSON.stringify(args)}
Result: ${result.slice(0, 2000)}

Provide a 1-2 sentence summary of the key information.
  `;

  // 使用快速模型生成摘要
  return await callLlm(prompt, { model: getFastModel() });
}
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **Token 節省** | 迭代 prompt 大幅縮短 |
| **準確性保持** | 最終答案使用完整數據 |
| **成本優化** | 摘要使用快速小模型 |
| **平衡效率與質量** | 不犧牲最終結果質量 |

### 適用場景

- 工具返回大量數據的場景
- 需要多輪迭代的複雜任務
- 希望控制 API 成本的應用

---

## 4. Tool Registry 模式

### 概念

集中式工具管理，支持：
- **條件式載入**：根據環境變量決定是否載入
- **豐富描述**：工具使用指引注入系統提示詞
- **優先級控制**：多個同類工具時選擇最佳

```typescript
// 集中式工具註冊
const registry = getToolRegistry(model);
// → [{ name: 'financial_search', tool, description }, { name: 'web_search', tool, description }]

// 獲取工具實例用於 LLM 綁定
const tools = getTools(model);

// 構建系統提示詞
const systemPrompt = buildSystemPrompt(model) + '\n\n' + buildToolDescriptions(model);
```

### 實現示例

```typescript
// src/tools/registry.ts
export interface RegisteredTool {
  name: string;
  tool: StructuredToolInterface;
  description: string;  // 豐富描述，注入系統提示詞
}

export function getToolRegistry(model: string): RegisteredTool[] {
  const tools: RegisteredTool[] = [
    {
      name: 'financial_search',
      tool: createFinancialSearch(model),
      description: FINANCIAL_SEARCH_DESCRIPTION,
    },
  ];

  // 條件式載入：Exa 優先，Tavily 後備
  if (process.env.EXASEARCH_API_KEY) {
    tools.push({
      name: 'web_search',
      tool: exaSearch,
      description: WEB_SEARCH_DESCRIPTION,
    });
  } else if (process.env.TAVILY_API_KEY) {
    tools.push({
      name: 'web_search',
      tool: tavilySearch,
      description: WEB_SEARCH_DESCRIPTION,
    });
  }

  return tools;
}
```

### 豐富描述

```typescript
// src/tools/descriptions/web-search.ts
export const WEB_SEARCH_DESCRIPTION = `
Search the web for current information on any topic.

## When to Use
- General knowledge questions not covered by financial_search
- Current events, breaking news, recent developments
- Technology updates, product announcements

## When NOT to Use
- Financial data queries (use financial_search instead)
- Queries about stock prices, company financials, SEC filings

## Usage Notes
- Provide specific, well-formed search queries
- Returns up to 5 results with URLs and content snippets
`.trim();
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **集中管理** | 所有工具在一處註冊 |
| **條件載入** | 避免缺少 API Key 時載入失敗 |
| **豐富指引** | LLM 能更好地選擇工具 |
| **優先級控制** | 多個同類工具時選擇最佳 |

### 適用場景

- 有多個可選工具的 Agent
- 需要根據環境配置調整工具的應用
- 希望引導 LLM 正確使用工具的場景

---

## 5. Lazy Initialization 模式

### 概念

工具延遲初始化，避免：
- 缺少 API Key 時啟動失敗
- 不必要的資源初始化
- 啟動時的網絡請求

```typescript
// 錯誤做法：模塊載入時初始化
const client = new ExaClient(process.env.EXA_API_KEY);  // 沒有 key 會報錯
export const tool = new ExaTool(client);

// 正確做法：延遲初始化
let client: ExaClient | null = null;
function getClient(): ExaClient {
  if (!client) {
    client = new ExaClient(process.env.EXA_API_KEY);
  }
  return client!;
}
```

### 實現示例

```typescript
// src/tools/search/exa.ts
let exaTool: ExaSearchResults | null = null;

function getExaTool(): ExaSearchResults {
  if (!exaTool) {
    const client = new Exa(process.env.EXASEARCH_API_KEY);
    exaTool = new ExaSearchResults({
      client,
      searchArgs: { numResults: 5, text: true },
    });
  }
  return exaTool!;
}

export const exaSearch = new DynamicStructuredTool({
  name: 'web_search',
  description: 'Search the web for current information.',
  schema: z.object({
    query: z.string().describe('The search query'),
  }),
  func: async (input) => {
    const result = await getExaTool().invoke(input.query);  // 首次調用時初始化
    return formatToolResult(result);
  },
});
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **啟動穩健** | 缺少 API Key 也能啟動 |
| **按需初始化** | 不使用的工具不初始化 |
| **單例保證** | 只初始化一次 |
| **錯誤延遲** | 錯誤在首次使用時才發生 |

### 適用場景

- 有可選工具的 Agent
- API Key 可能缺失的環境
- 希望快速啟動的應用

---

## 6. Event-driven UI 模式 (AsyncGenerator)

### 概念

使用 **AsyncGenerator** 產生事件流，UI 通過 `for await` 消費事件：

```typescript
// Agent 產生事件
async *run(query: string): AsyncGenerator<AgentEvent> {
  yield { type: 'thinking', message: '...' };
  yield { type: 'tool_start', tool: 'search', args: {...} };
  yield { type: 'tool_end', tool: 'search', result: '...' };
  yield { type: 'done', answer: '...' };
}

// UI 消費事件
for await (const event of agent.run(query)) {
  handleEvent(event);
}
```

### 實現示例

```typescript
// src/agent/types.ts
export type AgentEvent =
  | { type: 'thinking'; message: string }
  | { type: 'tool_start'; tool: string; args: Record<string, unknown> }
  | { type: 'tool_end'; tool: string; args: Record<string, unknown>; result: string; duration: number }
  | { type: 'tool_error'; tool: string; error: string }
  | { type: 'tool_limit'; tool: string; warning?: string; blocked: boolean }
  | { type: 'answer_start' }
  | { type: 'done'; answer: string; toolCalls: ToolCallRecord[]; iterations: number };

// src/hooks/useAgentRunner.ts
export function useAgentRunner() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);

  const runQuery = useCallback(async (query: string, model: string, signal?: AbortSignal) => {
    setIsRunning(true);
    setEvents([]);
    setAnswer(null);

    const agent = Agent.create({ model, signal });

    try {
      for await (const event of agent.run(query)) {
        if (signal?.aborted) break;

        setEvents(prev => [...prev, event]);

        if (event.type === 'done') {
          setAnswer(event.answer);
        }
      }
    } finally {
      setIsRunning(false);
    }
  }, []);

  return { events, isRunning, answer, runQuery };
}
```

### 對比回調模式

```typescript
// 回調模式 (v2.5)
interface AgentCallbacks {
  onThinking?: (message: string) => void;
  onToolStart?: (tool: string, args: unknown) => void;
  onToolEnd?: (tool: string, result: string) => void;
  onDone?: (answer: string) => void;
}

const agent = new Agent({ callbacks: {...} });
await agent.run(query);

// AsyncGenerator 模式 (v2.6)
const agent = Agent.create();
for await (const event of agent.run(query)) {
  switch (event.type) {
    case 'thinking': /* ... */ break;
    case 'tool_start': /* ... */ break;
    case 'done': /* ... */ break;
  }
}
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **簡化接口** | 不需要定義大量回調接口 |
| **自然取消** | 通過 AbortSignal 自然支持取消 |
| **類型安全** | 事件類型聯合類型提供完整類型檢查 |
| **統一模式** | 所有事件通過同一管道 |
| **測試友好** | 可以收集所有事件進行斷言 |

### 適用場景

- 需要即時反饋的 UI 應用
- 希望支持取消操作的場景
- 需要統一事件處理的應用

---

## 7. Token Budget 模式 (LLM 上下文選擇)

### 概念

Context Compaction 的延伸保護：當所有完整數據的 token 總量超出 LLM 窗口預算時，讓 **LLM 選擇最相關的結果** 保持完整，其餘降級為摘要：

```
完整數據 [A, B, C, D, E] → 估算 token 總量
        ↓
    ≤ 150k tokens → 全部完整包含 (正常路徑)
        ↓
    > 150k tokens → LLM 選擇 [A, C] 為最重要
        ↓
    最終 prompt = [A完整, B摘要, C完整, D摘要, E摘要]
        ↓
    LLM 選擇失敗 → 全部降級為摘要 (安全降級)
```

### 實現示例

```typescript
// src/utils/tokens.ts
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 3.5);  // 保守估算
}
export const TOKEN_BUDGET = 150_000;

// src/agent/agent.ts
private async buildFullContextForAnswer(query: string, scratchpad: Scratchpad): Promise<string> {
  const contexts = scratchpad.getFullContextsWithSummaries();
  const totalTokens = contexts.reduce(
    (sum, ctx) => sum + estimateTokens(ctx.result), 0
  );

  // 預算內：全部完整包含（行為不變）
  if (totalTokens <= TOKEN_BUDGET) {
    return this.formatFullContexts(contexts);
  }

  // 超出預算：LLM 選擇最重要的結果
  try {
    return await this.buildLLMSelectedContext(query, contexts);
  } catch {
    // 安全降級：全部用摘要
    return this.formatSummariesOnly(contexts);
  }
}
```

### LLM 選擇邏輯

```typescript
private async buildLLMSelectedContext(
  query: string,
  contexts: ToolContextWithSummary[]
): Promise<string> {
  // 準備摘要列表（附 token 成本）供 LLM 選擇
  const summaries = contexts.map(ctx => ({
    index: ctx.index,
    toolName: ctx.toolName,
    summary: ctx.llmSummary,
    tokenCost: estimateTokens(ctx.result),
  }));

  // 請 LLM 選擇最相關的結果
  const selectionPrompt = buildContextSelectionPrompt(query, summaries);
  const response = await callLlm(selectionPrompt, {
    model: getFastModel(this.modelProvider, this.model),
  });

  const selectedIndices = new Set<number>(JSON.parse(String(response)));

  // 選中的用完整數據，其餘用摘要
  let usedTokens = 0;
  const fullResults: string[] = [];
  const summaryResults: string[] = [];

  for (const ctx of contexts) {
    const tokenCost = estimateTokens(ctx.result);
    if (selectedIndices.has(ctx.index) && usedTokens + tokenCost <= TOKEN_BUDGET) {
      fullResults.push(formatContext(ctx, true));   // 完整
      usedTokens += tokenCost;
    } else {
      summaryResults.push(formatContext(ctx, false)); // 摘要
    }
  }

  return combineContextSections(fullResults, summaryResults);
}
```

### 三級降級策略

| 級別 | 條件 | 行為 |
|------|------|------|
| **正常** | 總 token ≤ 150k | 所有結果完整包含（行為不變） |
| **選擇性** | 總 token > 150k | LLM 選擇最重要的結果保持完整 |
| **安全降級** | LLM 選擇失敗 | 全部使用摘要 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **漸進式降級** | 不是全有全無，而是保留最重要的數據 |
| **透明決策** | LLM 看到所有摘要和成本後做出選擇 |
| **安全保底** | 雙重 fallback 確保不會崩潰 |
| **正常路徑零開銷** | 只在超出預算時才觸發 LLM 選擇 |

### 適用場景

- 工具返回數據量可能很大且不可預測的場景
- 多輪工具調用累積大量數據的 Agent
- 需要平衡完整性與上下文窗口限制的應用

---

## 8. Graceful Exit 模式 (軟引導式工具限制)

### 概念

不硬性阻止工具調用，而是給 LLM **足夠的上下文信息**，讓它自己做出合理決策。核心哲學：**信任 LLM 的判斷**。

```
工具調用請求
      ↓
  ┌─────────────────────────────────────┐
  │ canCallTool() → 永遠 allowed: true │
  │                                     │
  │ 三種警告場景：                       │
  │ 1. 接近限制 → "approaching 2/3"    │
  │ 2. 相似查詢 → "very similar to..."  │
  │ 3. 超過限制 → "has been called 3x"  │
  │                                     │
  │ 警告注入到下一輪 iteration prompt    │
  └─────────────────────────────────────┘
      ↓
  LLM 自行決定是否繼續調用
```

### 設計演進

此模式經歷了 3 個版本的設計迭代（2 天內完成）：

```
v1 (01-29): 硬限制
  工具調用 >= 3 → blocked: true → Agent 被阻止
  問題: LLM 有時確實需要更多調用

v2 (01-29): 軟限制 + 警告
  工具調用 >= 3 → warning 文字 → LLM 看到但仍被阻止
  問題: 仍然有硬阻止，違反「信任 LLM」原則

v3 (01-30): 純引導 (最終版)
  移除 blocked: true → 所有調用都允許
  只提供引導性警告 → LLM 自行判斷
```

### 實現示例

```typescript
// src/agent/scratchpad.ts
interface ToolLimitConfig {
  maxCallsPerTool: number;       // 建議上限 (默認 3)
  similarityThreshold: number;   // Jaccard 相似度閾值 (默認 0.7)
}

// 永遠允許，只提供警告
canCallTool(toolName: string, query?: string): { allowed: boolean; warning?: string } {
  const currentCount = this.toolCallCounts.get(toolName) ?? 0;
  const maxCalls = this.limitConfig.maxCallsPerTool;

  // 場景 1: 超過建議上限
  if (currentCount >= maxCalls) {
    return {
      allowed: true,  // 永遠允許
      warning: `Tool '${toolName}' has been called ${currentCount} times (suggested limit: ${maxCalls}). ` +
        `Consider: (1) trying a different tool, (2) different search terms, or (3) proceeding with what you have.`,
    };
  }

  // 場景 2: 查詢相似度偵測
  if (query) {
    const similarQuery = this.findSimilarQuery(query, this.toolQueries.get(toolName) ?? []);
    if (similarQuery) {
      return {
        allowed: true,
        warning: `This query is very similar to a previous '${toolName}' call. Consider a different approach.`,
      };
    }
  }

  // 場景 3: 接近上限
  if (currentCount === maxCalls - 1) {
    return {
      allowed: true,
      warning: `Approaching suggested limit for '${toolName}' (${currentCount + 1}/${maxCalls}).`,
    };
  }

  return { allowed: true };
}
```

### 查詢相似度偵測 (Jaccard)

```typescript
// 將查詢文字分詞後計算 Jaccard 相似度
private findSimilarQuery(newQuery: string, previousQueries: string[]): string | null {
  const newWords = this.tokenize(newQuery);

  for (const prevQuery of previousQueries) {
    const prevWords = this.tokenize(prevQuery);
    const intersection = [...newWords].filter(w => prevWords.has(w)).length;
    const union = new Set([...newWords, ...prevWords]).size;
    const similarity = intersection / union;  // Jaccard similarity

    if (similarity >= 0.7) {  // 閾值
      return prevQuery;
    }
  }
  return null;
}

private tokenize(query: string): Set<string> {
  return new Set(
    query.toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(w => w.length > 2)
  );
}
```

### 警告注入到 Prompt

```typescript
// 工具使用狀態注入到迭代 prompt
formatToolUsageForPrompt(): string | null {
  const statuses = this.getToolUsageStatus();
  if (statuses.length === 0) return null;

  const lines = statuses.map(s => {
    const status = s.callCount >= s.maxCalls
      ? `${s.callCount} calls (over suggested limit of ${s.maxCalls})`
      : `${s.callCount}/${s.maxCalls} calls`;
    return `- ${s.toolName}: ${status}`;
  });

  return `## Tool Usage This Query\n\n${lines.join('\n')}\n\n` +
    `Note: If a tool isn't returning useful results, consider trying a different approach.`;
}
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **靈活性** | LLM 在確實需要時仍可繼續調用 |
| **防重複** | Jaccard 相似度偵測防止無效重試 |
| **透明性** | LLM 看到完整的工具使用統計 |
| **信任 LLM** | 提供信息而非強制規則 |

### 關鍵洞察

> **信任 LLM 的判斷** 優於硬性規則。與其用代碼邏輯阻止工具調用，不如給 LLM 足夠的上下文信息（已調用次數、相似查詢、替代建議），讓它自己做出合理決策。此模式在 2 天內經歷了從「硬限制」到「軟引導」的演變，印證了這個原則。

### 適用場景

- Agent 需要防止無限重試循環的場景
- 工具調用有成本考量（付費 API）的應用
- 希望平衡自主性與安全性的 Agent

---

## 9. Skills System 模式 (Plugin 式工作流)

### 概念

將複雜的多步驟分析封裝為 **SKILL.md** 文件，通過三級目錄發現機制實現 Plugin 式擴展：

```
啟動時: 掃描三級目錄 → 讀取 YAML frontmatter (name + description)
                     → 注入系統提示詞 (輕量)

調用時: 根據 name 載入完整 SKILL.md body → 執行多步工作流

目錄優先級:
  src/skills/           (builtin)  ← 內建
  ~/.dexter/skills/     (user)     ← 用戶級
  .dexter/skills/       (project)  ← 專案級覆蓋
```

### SKILL.md 格式

```markdown
---
name: dcf-valuation
description: Performs DCF valuation analysis. Triggers when user asks for fair value,
  intrinsic value, DCF, or valuation.
---

# DCF Valuation Skill

## Step 1: Gather Financial Data
Call the `financial_search` tool with these queries:
- "[TICKER] annual cash flow statements for the last 5 years"
- "[TICKER] financial metrics snapshot"
...

## Step 2: Calculate FCF Growth Rate
...

## Step 8: Output Format
Present a structured summary including:
1. Valuation Summary: Current price vs. fair value
2. Key Inputs Table
3. Sensitivity Matrix
```

### 實現示例

```typescript
// src/skills/types.ts
type SkillSource = 'builtin' | 'user' | 'project';

interface SkillMetadata {
  name: string;           // "dcf-valuation"
  description: string;    // 觸發條件描述
  path: string;           // SKILL.md 絕對路徑
  source: SkillSource;    // 來源層級
}

interface Skill extends SkillMetadata {
  instructions: string;   // 完整 SKILL.md body (按需載入)
}

// src/skills/registry.ts
const SKILL_DIRECTORIES = [
  { path: __dirname, source: 'builtin' },                    // 內建 skills
  { path: join(homedir(), '.dexter', 'skills'), source: 'user' },    // 用戶級
  { path: join(process.cwd(), '.dexter', 'skills'), source: 'project' }, // 專案級
];

let skillMetadataCache: Map<string, SkillMetadata> | null = null;

export function discoverSkills(): SkillMetadata[] {
  if (skillMetadataCache) return Array.from(skillMetadataCache.values());

  skillMetadataCache = new Map();

  for (const { path, source } of SKILL_DIRECTORIES) {
    const skills = scanSkillDirectory(path, source);
    for (const skill of skills) {
      skillMetadataCache.set(skill.name, skill);  // 後者覆蓋前者
    }
  }

  return Array.from(skillMetadataCache.values());
}

// 按需載入完整指令
export function getSkill(name: string): Skill | undefined {
  if (!skillMetadataCache) discoverSkills();
  const metadata = skillMetadataCache?.get(name);
  if (!metadata) return undefined;
  return loadSkillFromPath(metadata.path, metadata.source);
}
```

### 去重機制

```typescript
// src/agent/scratchpad.ts
// 每個 Skill 每次查詢只執行一次
hasExecutedSkill(skillName: string): boolean {
  return this.readEntries().some(
    e => e.type === 'tool_result' && e.toolName === 'skill' && e.args?.skill === skillName
  );
}

// src/agent/agent.ts (在 executeToolCalls 中)
if (toolName === 'skill') {
  const skillName = toolArgs.skill as string;
  if (scratchpad.hasExecutedSkill(skillName)) continue;  // 跳過重複
}
```

### 設計決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| **元數據格式** | YAML frontmatter | 標準格式，易解析 |
| **指令格式** | Markdown body | 自然語言，LLM 友好 |
| **載入策略** | 啟動掃描元數據，按需載入完整內容 | 平衡啟動速度和記憶體 |
| **覆蓋順序** | builtin → user → project | 後者覆蓋前者，專案可客制化 |
| **去重** | Scratchpad 追蹤 | 防止同一 Skill 重複執行 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **可擴展** | 新增 Skill 只需添加目錄和 SKILL.md |
| **可覆蓋** | 用戶或專案可覆蓋內建 Skill 行為 |
| **輕量啟動** | 啟動時只讀 YAML frontmatter，不載入完整指令 |
| **LLM 原生** | Markdown 格式對 LLM 天然友好 |
| **可調試** | SKILL.md 是人類可讀的純文本 |

### 適用場景

- 需要預定義多步驟分析工作流的 Agent
- 希望用戶可自定義分析模板的應用
- 不同專案需要不同分析流程的場景

---

## 10. Context Clearing 模式 (取代摘要迭代)

### 概念

取代 Context Compaction 的摘要策略：**保留完整的工具結果在迭代 prompt 中**，當 token 總量超過閾值時，清除最舊的結果而非將所有結果摘要化：

```
迭代 N: 工具結果 [A完整, B完整, C完整, D完整]
        ↓
    估算 token (系統提示詞 + 查詢 + 所有工具結果)
        ↓
    ≤ CONTEXT_THRESHOLD → 保留全部
        ↓
    > CONTEXT_THRESHOLD → clearOldestToolResults(keepCount=3)
        ↓
    結果: [A清除, B完整, C完整, D完整]
        ↓
    yield { type: 'context_cleared', clearedCount: 1, keptCount: 3 }
```

### 實現示例

```typescript
// src/agent/agent.ts
let fullToolResults = scratchpad.getToolResults();
const estimatedTokens = estimateTokens(this.systemPrompt + query + fullToolResults);

if (estimatedTokens > CONTEXT_THRESHOLD) {
  const clearedCount = scratchpad.clearOldestToolResults(KEEP_TOOL_USES);
  if (clearedCount > 0) {
    yield { type: 'context_cleared', clearedCount, keptCount: KEEP_TOOL_USES };
    fullToolResults = scratchpad.getToolResults();  // 重新獲取（跳過已清除的）
  }
}

// 下一輪 prompt 使用完整結果（而非摘要）
currentPrompt = buildIterationPrompt(query, fullToolResults, toolUsageStatus);
```

```typescript
// src/agent/scratchpad.ts
clearOldestToolResults(keepCount: number): number {
  const toolIndices = this.getToolResultIndices();  // 所有未清除的工具結果索引
  const toClear = Math.max(0, toolIndices.length - keepCount);

  // 標記最舊的為已清除（記憶體操作，JSONL 不受影響）
  for (let i = 0; i < toClear; i++) {
    this.clearedIndices.add(toolIndices[i]);
  }
  return toClear;
}

getToolResults(): string {
  return this.entries
    .map((entry, i) => {
      if (this.clearedIndices.has(i)) {
        return `[Tool result #${i} cleared from context]`;  // 佔位符
      }
      return formatToolResult(entry);  // 完整結果
    })
    .join('\n');
}
```

### 對比 Context Compaction

| 面向 | Context Compaction (v2.6.0) | Context Clearing (v2.6.2) |
|------|---------------------------|--------------------------|
| **迭代 prompt** | LLM 生成的摘要 | 完整工具結果 |
| **信息損失** | 有（摘要必然丟失細節） | 無（清除的是最舊的完整結果） |
| **額外 LLM 呼叫** | 每次工具執行後一次 | 無 |
| **成本** | 較高（摘要生成費用） | 較低 |
| **超出閾值處理** | 所有結果都是摘要 | 清除最舊，保留最近完整結果 |
| **JSONL 文件** | 不受影響 | 不受影響（清除是記憶體操作） |

### 優勢

| 優勢 | 說明 |
|------|------|
| **更高推理準確性** | LLM 看到完整數據而非摘要 |
| **零額外 LLM 呼叫** | 不需要生成摘要，降低成本和延遲 |
| **保留調試能力** | JSONL 文件保持完整歷史 |
| **漸進式清除** | 不是全有全無，而是先清除最舊的 |

### 適用場景

- LLM 上下文窗口足夠大（128k+）的場景
- 工具結果的細節對推理至關重要的應用
- 希望降低摘要帶來的信息損失的 Agent

---

## 11. Subagent 模式 (LLM 路由器)

### 概念

將複雜工具封裝為 **Subagent**——外部 Agent 只看到一個簡單工具，內部由獨立的 LLM 做路由和子工具分派：

```
外部 Agent:
  "Apple 的 P/E 和負債比率？" → financial_metrics 工具
                                     ↓
內部 Subagent:                    LLM 路由器
  分析查詢 → 選擇子工具        → get_key_ratios_snapshot
             (並行執行)          → get_balance_sheets
                                     ↓
                                合併結果 → 返回統一回應
```

### 實現示例

```typescript
// src/tools/finance/financial-metrics.ts
export function createFinancialMetrics(model: string) {
  return new DynamicStructuredTool({
    name: 'financial_metrics',
    description: 'Get fundamental financial data...',
    schema: z.object({ query: z.string() }),
    func: async (input, config) => {
      const onProgress = config?.metadata?.onProgress;
      const llm = createChatModel(model);

      // Step 1: LLM 路由 — 讓 LLM 決定調用哪些子工具
      onProgress?.('Analyzing query...');
      const routingResponse = await llm.bindTools(subTools).invoke([
        new SystemMessage(ROUTING_PROMPT),
        new HumanMessage(input.query),
      ]);

      // Step 2: 並行執行選中的子工具
      const toolCalls = routingResponse.tool_calls ?? [];
      onProgress?.(`Fetching from ${toolCalls.length} sources...`);
      const results = await Promise.all(
        toolCalls.map(tc => executeSubTool(tc))
      );

      // Step 3: 合併結果
      return combineResults(results);
    },
  });
}
```

### Read Filings 兩步式 Subagent

```typescript
// src/tools/finance/read-filings.ts
// Step 1: 搜索文件元數據
const filings = await llm.bindTools([get_filings]).invoke([
  new SystemMessage('Search for relevant SEC filings'),
  new HumanMessage(query),
]);

// Step 2: 選擇性讀取 items
const items = await llm.bindTools([get_10K_items, get_10Q_items, get_8K_items]).invoke([
  new SystemMessage('Select and read relevant filing items'),
  new HumanMessage(`Query: ${query}\nAvailable filings: ${JSON.stringify(filings)}`),
]);
```

### Progress Channel 整合

Subagent 工具透過 `onProgress` 回調發送中間進度，Agent 經由 Progress Channel 橋接為事件流：

```typescript
// src/utils/progress-channel.ts
interface ProgressChannel {
  emit: (message: string) => void;           // 同步：Subagent 發送進度
  close: () => void;                         // 標記完成
  [Symbol.asyncIterator](): AsyncIterator<string>;  // 異步：Agent 消費
}

// Agent 端使用
const channel = createProgressChannel();
executeTool(toolCall, { metadata: { onProgress: channel.emit } });
for await (const msg of channel) {
  yield { type: 'tool_progress', tool: toolCall.name, message: msg };
}
```

### 設計決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| **為什麼不直接暴露子工具？** | 封裝為 Subagent | 降低外部 Agent 認知負擔 |
| **為什麼用 LLM 路由？** | 查詢多樣性太高 | 規則難以涵蓋所有情況 |
| **為什麼並行執行子工具？** | Promise.all | 子工具間通常無依賴 |
| **進度如何傳遞？** | Progress Channel | 橋接同步 emit 到異步事件流 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **外部簡潔** | 外部 Agent 只看到一個工具 |
| **內部強大** | 可分派到 6+ 個子工具 |
| **智能路由** | LLM 理解自然語言查詢的意圖 |
| **可觀察** | Progress Channel 串流中間步驟 |
| **可擴展** | 新增子工具不影響外部介面 |

### 適用場景

- 一個領域有多個 API 端點，選擇邏輯複雜的場景
- 希望外部 Agent 介面簡潔的應用
- 需要中間步驟可觀察性的場景

---

## 12. Repository-Layer Cache 模式

### 概念

在 API 呼叫層面快取回應到本地文件系統，對歷史和不可變數據實現零重複請求：

```
API 請求 (endpoint, params)
        ↓
  readCache(endpoint, params)
        ↓
    命中 → 返回快取數據（跳過網路請求）
        ↓
    未命中 → fetch API → writeCache(endpoint, params, data)
```

### 實現示例

```typescript
// src/utils/cache.ts
const CACHE_DIR = '.dexter/cache';

export function readCache(endpoint: string, params: Record<string, unknown>): CacheEntry | null {
  const key = buildCacheKey(endpoint, params);
  const filePath = join(CACHE_DIR, endpoint, `${key}.json`);

  try {
    const data = JSON.parse(readFileSync(filePath, 'utf-8'));
    return data;
  } catch {
    // 自癒：損壞文件自動移除
    try { unlinkSync(filePath); } catch {}
    return null;
  }
}

export function writeCache(
  endpoint: string,
  params: Record<string, unknown>,
  data: unknown,
  url: string,
): void {
  const key = buildCacheKey(endpoint, params);
  const dir = join(CACHE_DIR, endpoint);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${key}.json`), JSON.stringify({
    endpoint, params, data, url,
    cachedAt: new Date().toISOString(),
  }, null, 2));
}

// 確定性 hash：相同 params 永遠映射到相同文件
export function buildCacheKey(endpoint: string, params: Record<string, unknown>): string {
  const ticker = (params.ticker as string) || 'unknown';
  const hash = createHash('md5').update(JSON.stringify(sortedParams(params))).digest('hex').slice(0, 12);
  return `${ticker}_${hash}`;
}
```

### 快取策略

| 資料類型 | 快取條件 | 理由 |
|----------|----------|------|
| 歷史股價 | `endDate < today` | 歷史數據已定型 |
| 歷史加密貨幣價格 | `endDate < today` | 同上 |
| SEC Filing Items | 始終 | 文件內容不可變 |
| 即時報價/指標 | **永不** | 需要最新數據 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **零重複請求** | 相同歷史查詢不再消耗 API 額度 |
| **快速回應** | 快取命中 < 1ms vs API 500-2000ms |
| **確定性** | MD5 hash 確保相同 params 命中相同快取 |
| **自癒** | 損壞文件自動移除 |
| **Opt-in** | 只有標記 `cacheable` 的請求才快取 |

### 適用場景

- API 有速率限制或按次計費的場景
- 查詢歷史或不可變數據的應用
- 重複分析同一標的的工作流

---

## 13. Prompt Caching 模式 (Provider-Level)

### 概念

利用 LLM Provider 的 prompt caching 功能，在多輪 Agent Loop 迭代中降低系統提示詞的重複傳輸成本：

```
迭代 1: [系統提示詞 ■■■■■■■■] + [用戶 prompt] → 全價
迭代 2: [系統提示詞 (cached)] + [用戶 prompt] → 90% 折扣
迭代 3: [系統提示詞 (cached)] + [用戶 prompt] → 90% 折扣
...
```

### 實現示例

```typescript
// src/model/llm.ts
function buildAnthropicMessages(systemPrompt: string, userPrompt: string) {
  return [
    new SystemMessage({
      content: [{
        type: 'text',
        text: systemPrompt,
        cache_control: { type: 'ephemeral' },  // 標記為可快取前綴
      }]
    }),
    new HumanMessage(userPrompt),
  ];
}

// 根據模型選擇策略
async function callLLM(model: string, systemPrompt: string, userPrompt: string) {
  if (model.startsWith('claude-')) {
    // Anthropic: 手動標記 cache_control
    return llm.invoke(buildAnthropicMessages(systemPrompt, userPrompt));
  } else {
    // OpenAI / Gemini: 自動快取，無需額外標記
    return llm.invoke(buildStandardMessages(systemPrompt, userPrompt));
  }
}
```

### Provider 差異

| Provider | 快取方式 | 開發者操作 |
|----------|----------|-----------|
| Anthropic | `cache_control: ephemeral` | 需手動標記 |
| OpenAI | 自動前綴快取 | 無需操作 |
| Google | 自動快取 | 無需操作 |
| OpenRouter | 取決於下游 Provider | 透傳 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **成本降低 90%** | 系統提示詞在多輪迭代中只計費一次 |
| **零代碼改動** | 對業務邏輯透明 |
| **自動失效** | `ephemeral` 策略，Provider 管理 TTL |

### 適用場景

- Agent Loop 多輪迭代（系統提示詞重複傳送）
- 系統提示詞較長（工具描述、規則等）
- 成本敏感的應用

---

## 14. Provider Registry 模式 (集中式 Provider 元數據)

### 概念

將所有 LLM Provider 的元數據（ID、顯示名稱、模型前綴、API Key 環境變量、快速模型）集中到**單一來源**，消除散落在多個模塊中的重複定義：

```
重構前：Provider 資訊散落 3 處
  llm.ts          → MODEL_FACTORIES: { 'claude-': ..., 'gemini-': ... }
  env.ts          → PROVIDER_ENV_VARS: { anthropic: 'ANTHROPIC_API_KEY', ... }
  ModelSelector   → PROVIDERS: [{ displayName: 'Anthropic', models: [...] }]

重構後：單一來源
  providers.ts    → PROVIDERS: ProviderDef[]
  llm.ts          → import { resolveProvider } from './providers'
  env.ts          → import { getProviderById } from './providers'
  ModelSelector   → import { PROVIDERS } from './providers'
```

### 實現示例

```typescript
// src/providers.ts
interface ProviderDef {
  id: string;           // 'openai', 'anthropic', 'deepseek', 'moonshot', ...
  displayName: string;  // 人類可讀名稱
  modelPrefix: string;  // 路由前綴 ('claude-', 'deepseek-', 'kimi-', '')
  apiKeyEnvVar?: string; // 環境變量名，Ollama 無需
  fastModel?: string;   // 輕量任務的快速模型
}

const PROVIDERS: ProviderDef[] = [
  { id: 'openai', displayName: 'OpenAI', modelPrefix: '', apiKeyEnvVar: 'OPENAI_API_KEY', fastModel: 'gpt-4o-mini' },
  { id: 'anthropic', displayName: 'Anthropic', modelPrefix: 'claude-', apiKeyEnvVar: 'ANTHROPIC_API_KEY', fastModel: 'claude-3-5-haiku-latest' },
  { id: 'deepseek', displayName: 'DeepSeek', modelPrefix: 'deepseek-', apiKeyEnvVar: 'DEEPSEEK_API_KEY', fastModel: 'deepseek-chat' },
  // ...
];

// 核心函數
export function resolveProvider(modelName: string): ProviderDef {
  return PROVIDERS.find(p => p.modelPrefix && modelName.startsWith(p.modelPrefix))
    ?? PROVIDERS.find(p => p.id === 'openai')!;  // fallback OpenAI (空前綴)
}
```

### 新增 Provider 的步驟

只需一步：在 `PROVIDERS` 陣列添加一筆 `ProviderDef`，然後在 `llm.ts` 的 `MODEL_FACTORIES` 添加工廠函數。所有消費端自動適配。

### 優勢

| 優勢 | 說明 |
|------|------|
| **DRY** | 消除 3+ 處的重複定義 |
| **零遺漏** | 新增 Provider 不會忘記更新某處 |
| **類型安全** | `ProviderDef` 接口確保必要字段 |
| **可發現** | 所有支援的 Provider 一目了然 |

### 適用場景

- 支持多個 LLM Provider 的應用
- Provider 資訊在 3+ 處消費的場景
- 預期會持續新增 Provider 的專案

---

## 15. Channel Plugin 模式 (Gateway 頻道抽象)

### 概念

將通訊頻道抽象為 **泛型 Plugin 接口**，使 Gateway 核心邏輯與具體頻道實現解耦：

```
Gateway Core (gateway.ts)
    ↓ 使用
ChannelPlugin<TConfig, TAccount> (泛型接口)
    ↓ 實現
WhatsApp Plugin          未來: Telegram Plugin
  ├── session.ts           ├── session.ts
  ├── inbound.ts           ├── inbound.ts
  └── outbound.ts          └── outbound.ts
```

### 實現示例

```typescript
// src/gateway/channels/types.ts
interface ChannelPlugin<TConfig, TAccount> {
  id: ChannelId;                                    // 'whatsapp', 'telegram', ...
  config: ChannelConfigAdapter<TConfig, TAccount>;  // 帳號配置解析
  gateway: ChannelGatewayAdapter<TAccount>;         // 帳號生命週期
  status?: { defaultRuntime?: ChannelRuntimeSnapshot };
}

interface ChannelGatewayAdapter<TAccount> {
  startAccount(account: TAccount, ctx: StartAccountContext): Promise<void>;
  stopAccount(accountId: string): Promise<void>;
}
```

### 訊息處理管線

```
入站訊息 (WhatsApp WebSocket)
    ↓
inbound.ts: 文字提取 + LID 解析 + 去重
    ↓
access-control.ts: DM/群組策略判定
    ↓
routing/resolve-route.ts: binding 匹配 → agentId + sessionKey
    ↓
agent-runner.ts: Turn 序列化 → Agent.run() → 收集回答
    ↓
outbound.ts: assertOutboundAllowed() → 發送回覆
```

### 穩定性模式

| 機制 | 實現 | 用途 |
|------|------|------|
| **指數退避重連** | `reconnect.ts` | WebSocket 斷開後自動恢復 |
| **看門狗計時器** | `runtime.ts` | 偵測靜默斷開（30min 無訊息） |
| **憑證備份** | `auth-store.ts` | 防止 `creds.json` 損壞 |
| **離線訊息過濾** | `inbound.ts` | 重連後不回覆歷史訊息 |
| **訊息去重** | `dedupe.ts` | TTL 20min / max 5000 條 |
| **出站安全** | `outbound.ts` | 強制白名單 + 非群組檢查 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **可擴展** | 新增頻道只需實現 `ChannelPlugin` 接口 |
| **類型安全** | 泛型確保配置和帳號類型一致 |
| **業務邏輯共用** | 存取控制、路由、Session 管理與頻道無關 |

### 適用場景

- 需要支持多個通訊頻道的 AI Agent
- 長駐服務需要穩定性工程的場景
- 需要存取控制和 Session 隔離的應用

---

## 16. 安全內容包裝模式 (外部內容邊界防護)

### 概念

當 LLM Agent 需要處理**外部不可信內容**（網頁、API 回應、用戶轉發的訊息）時，用明確的安全邊界標記包裝，並偵測可疑的 prompt injection 模式：

```
外部內容
    ↓
detectSuspiciousPatterns(content)  → 標記可疑模式
    ↓
replaceMarkers(content)           → 清理偽造邊界
    ↓
<<<EXTERNAL_UNTRUSTED_CONTENT>>>
⚠️ SECURITY WARNING: This content is from an external source...
[content]
<<<END_EXTERNAL_UNTRUSTED_CONTENT>>>
```

### 實現示例

```typescript
// src/tools/fetch/external-content.ts

// 12 種可疑模式
const SUSPICIOUS_PATTERNS = [
  /ignore\s+(all\s+)?previous\s+instructions/i,
  /you\s+are\s+now\s+a/i,
  /system\s*:\s*you/i,
  /\brm\s+-rf\b/,
  /delete\s+all\s+emails/i,
  /transfer\s+\$?\d+/i,
  // ...
];

export function detectSuspiciousPatterns(content: string): string[] {
  return SUSPICIOUS_PATTERNS
    .filter(pattern => pattern.test(content))
    .map(pattern => pattern.source);
}

// 邊界標記清理（防止內容偽造邊界，包含 fullwidth Unicode 變體）
export function replaceMarkers(content: string): string {
  return content
    .replace(/<<<EXTERNAL_UNTRUSTED_CONTENT>>>/g, '[[MARKER_SANITIZED]]')
    .replace(/＜＜＜EXTERNAL_UNTRUSTED_CONTENT＞＞＞/g, '[[MARKER_SANITIZED]]');
}
```

### 對比不同工具的安全策略

| 工具 | 安全包裝 | 可疑模式偵測 | 原因 |
|------|----------|------------|------|
| `web_fetch` | ✅ 完整包裝 + 警告 | ✅ 12 種模式 | 直接擷取任意 URL |
| `web_search` | ✅ 邊界標記 | ❌ | 搜索引擎已初步過濾 |
| `browser` | ❌ | ❌ | 用戶主動瀏覽，有 UI 確認 |

### 優勢

| 優勢 | 說明 |
|------|------|
| **防 prompt injection** | 明確告知 LLM 內容邊界 |
| **防邊界偽造** | 清理內容中的邊界標記（含 Unicode 變體） |
| **分級策略** | 不同來源使用不同安全等級 |

### 適用場景

- Agent 需要處理任意 URL 內容的場景
- 結合外部 API 回應的工具
- 任何讓 LLM 接觸不可信文本的應用

---

## 17. Agent 分解模式 (職責拆分)

### 概念

隨著 Agent 核心邏輯膨脹，將其拆分為**三個職責清晰的模塊**，Agent 本身只負責編排：

```
重構前：agent.ts (367 行)
  ├── 運行狀態管理 (散落的局部變數)
  ├── 工具調度迴圈 (Progress Channel + 事件發射)
  └── 最終答案格式化

重構後：
  ┌─────────────────┐
  │   Agent (~219)   │  ← 只負責編排：while 迴圈 + LLM 呼叫 + 委派
  └───┬─────┬────┬──┘
      ▼     ▼    ▼
  ┌───────┐ ┌──────────┐ ┌────────────────┐
  │RunCtx │ │ToolExec  │ │FinalAnswerCtx  │
  │(狀態) │ │(調度)    │ │(格式化)        │
  └───────┘ └──────────┘ └────────────────┘
```

### 實現示例

```typescript
// src/agent/run-context.ts — 狀態容器
interface RunContext {
  readonly query: string;
  readonly scratchpad: Scratchpad;
  readonly tokenCounter: TokenCounter;
  readonly startTime: number;
  iteration: number;
}

export function createRunContext(query: string): RunContext {
  return {
    query,
    scratchpad: new Scratchpad(query),
    tokenCounter: new TokenCounter(),
    startTime: Date.now(),
    iteration: 0,
  };
}

// src/agent/tool-executor.ts — 工具調度引擎
class AgentToolExecutor {
  async *executeAll(response, ctx: RunContext): AsyncGenerator<AgentEvent> {
    for (const toolCall of response.tool_calls) {
      yield* this.executeSingle(toolCall.name, toolCall.args, ctx);
    }
  }
  // 每個工具：canCallTool → tool_start → Progress Channel → invoke → tool_end
}

// src/agent/final-answer-context.ts — 上下文格式化
export function buildFinalAnswerContext(scratchpad: Scratchpad): string {
  const contexts = scratchpad.getFullContexts().filter(ctx => !isError(ctx));
  if (contexts.length === 0) return 'No data was gathered.';
  return contexts
    .map(ctx => `### ${describeToolCall(ctx)}\n\`\`\`json\n${prettyPrint(ctx.result)}\n\`\`\``)
    .join('\n\n');
}
```

### 拆分指引

| 信號 | 說明 | 行動 |
|------|------|------|
| 文件 > 300 行 | Agent 核心邏輯過多 | 考慮拆分 |
| 散落的局部變數 | 運行狀態缺乏結構 | 提取 RunContext |
| 工具調度 > 100 行 | 調度邏輯足夠獨立 | 提取 ToolExecutor |
| 格式化邏輯 > 50 行 | 格式化與編排無關 | 提取 ContextBuilder |

### 優勢

| 優勢 | 說明 |
|------|------|
| **職責清晰** | Agent=編排, ToolExecutor=調度, RunContext=狀態 |
| **可測試** | 各模塊可獨立單元測試 |
| **代碼量減少** | Agent 精簡 40% |
| **可讀性** | 每個文件 < 150 行，一目了然 |

### 適用場景

- Agent 核心文件超過 300 行的場景
- 工具調度邏輯複雜（Progress Channel、去重、限制檢查）的 Agent
- 需要對工具調度獨立測試的專案

---

## 18. Sandbox 模式 (文件系統安全邊界)

### 概念

當 AI Agent 需要操作文件系統（讀取、寫入、編輯文件）時，用 **Sandbox 安全邊界** 限制操作範圍，防止路徑逃逸和 symlink 攻擊：

```
Agent 請求操作 /path/to/file
    ↓
resolveSandboxPath({ filePath, cwd, root })
    ↓
1. 解析路徑 (相對→絕對)
2. 確認不超出 sandbox root (防止 ../../etc/passwd)
3. 逐層檢查 symlink (防止 symlink 逃逸)
    ↓
通過 → 執行文件操作
拒絕 → 拋出 Error("Path escapes sandbox root")
```

### 實現示例

```typescript
export function resolveSandboxPath(params: { filePath: string; cwd: string; root: string }) {
  const resolved = resolveToCwd(params.filePath, params.cwd);
  const rel = relative(resolvePath(params.root), resolved);

  if (rel.startsWith('..') || isAbsolute(rel)) {
    throw new Error(`Path escapes sandbox root: ${params.filePath}`);
  }
  return { resolved, relative: rel };
}

async function assertNoSymlink(relativePath: string, root: string): Promise<void> {
  const parts = relativePath.split(/[\\/]/).filter(Boolean);
  let current = root;
  for (const part of parts) {
    current = join(current, part);
    const stat = await lstat(current);
    if (stat.isSymbolicLink()) {
      throw new Error(`Symlink not allowed in sandbox path: ${current}`);
    }
  }
}
```

### 配套：Fuzzy Edit

LLM 產生的文字可能與源文件有微小差異（smart quotes、Unicode 破折號、多餘空白），edit 工具應寬容匹配：

```typescript
fuzzyFindText(content, oldText):
  1. 先嘗試精確匹配
  2. 失敗後 normalizeForFuzzyMatch(): 壓縮空白、替換 smart quotes/dashes
  3. 唯一性檢查：匹配必須唯一
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **防逃逸** | 路徑必須在 root 內 |
| **防 symlink** | 逐層檢查 |
| **寬容匹配** | fuzzy match 處理 LLM 微小差異 |

### 適用場景

- AI Agent 需要讀寫文件的場景
- 多租戶環境需要路徑隔離

---

## 19. Tool Approval 模式 (敏感工具審批)

### 概念

某些工具具有副作用（寫入文件、發送訊息），需要 **human-in-the-loop** 機制。三級授權平衡安全與體驗：

```
Agent 調用敏感工具
    ↓
已有 session 授權? → 直接執行
    ↓
向用戶顯示審批 UI
    ↓
┌──────────────┬──────────────────────┬──────────┐
│ allow-once   │ allow-session        │ deny     │
│ 執行本次     │ 加入 session 白名單   │ 中止     │
│ 下次再問     │ 後續不再問            │ Agent    │
└──────────────┴──────────────────────┴──────────┘
```

### 實現示例

```typescript
type ApprovalDecision = 'allow-once' | 'allow-session' | 'deny';

interface AgentConfig {
  requestToolApproval?: (request: { tool: string; args: Record<string, unknown> }) => Promise<ApprovalDecision>;
  sessionApprovedTools?: Set<string>;  // 跨查詢持久化
}

const TOOLS_REQUIRING_APPROVAL = ['write_file', 'edit_file'];

// ToolExecutor 中
if (requiresApproval(name) && !sessionApprovedTools.has(name)) {
  const decision = await requestToolApproval({ tool: name, args });
  if (decision === 'deny') { yield { type: 'tool_denied' }; return; }
  if (decision === 'allow-session') { sessionApprovedTools.add(name); }
}
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **安全** | 敏感操作需明確授權 |
| **體驗** | session 級別授權，只需確認一次 |
| **可擴展** | 工具列表可輕鬆添加 |

### 適用場景

- Agent 能執行有副作用的操作
- 需要用戶確認但不想每次都問

---

## 20. Controller Pattern (Observer 模式狀態管理)

### 概念

終端 UI 的狀態管理從 React Hooks 遷移到 **Controller 類 + onChange listener**（observer pattern）：

```
React Hooks 方式 (遷移前):           Controller 方式 (遷移後):
  useAgentRunner()    → 耦合 React     AgentRunnerController   → UI 框架無關
  useModelSelection() → 依賴渲染週期   ModelSelectionController → onChange 通知
  useInputHistory()   → 分散在組件中   InputHistoryController   → 集中管理
```

### 實現示例

```typescript
type ChangeListener = () => void;

class AgentRunnerController {
  private historyValue: HistoryItem[] = [];
  private workingStateValue: WorkingState = { status: 'idle' };
  private readonly onChange?: ChangeListener;

  get history(): HistoryItem[] { return this.historyValue; }
  get workingState(): WorkingState { return this.workingStateValue; }

  async runQuery(query: string): Promise<RunQueryResult> {
    this.workingStateValue = { status: 'thinking' };
    this.notify();  // 通知 UI 重新渲染
    // ... Agent 執行邏輯
  }

  private notify() { this.onChange?.(); }
}

// 任何 UI 框架都可以使用
const controller = new AgentRunnerController(config, history, () => tui.render());
```

### 優勢

| 優勢 | 說明 |
|------|------|
| **UI 框架解耦** | 不依賴 React/Ink/pi-mono |
| **狀態集中** | 每個功能域一個 Controller |
| **可測試** | 脫離 UI 獨立測試 |

### 適用場景

- 終端 UI 需要精確控制渲染
- 狀態管理需要與 UI 框架解耦

---

## 總結

| 模式 | 核心思想 | 主要優勢 |
|------|----------|----------|
| Agent Loop | 簡化的迭代循環，LLM 自決 | 簡化架構、靈活應對 |
| Scratchpad | JSONL 追加式日誌 | 崩潰安全、易於調試 |
| Context Compaction | 摘要迭代、完整答案 | 平衡效率與質量（已被 Context Clearing 取代） |
| Tool Registry | 集中管理、條件載入 | 穩健啟動、豐富指引 |
| Lazy Init | 延遲初始化 | 避免啟動失敗 |
| Event-driven UI | AsyncGenerator 事件流 | 簡化接口、支持取消 |
| Token Budget | LLM 選擇性保留完整數據 | 漸進式降級、零正常開銷 |
| Graceful Exit | 軟引導取代硬限制 | 信任 LLM、防重複調用 |
| Skills System | SKILL.md Plugin 式工作流 | 可擴展、可覆蓋、輕量 |
| Context Clearing | 保留完整結果、閾值清理最舊 | 更高推理準確性、零額外 LLM 呼叫 |
| Subagent | LLM 路由器分派子工具 | 外部簡潔、內部強大、可觀察 |
| Repository Cache | 文件級 API 回應快取 | 零重複請求、確定性、自癒 |
| Prompt Caching | Provider 級系統提示詞快取 | 多輪迭代成本降 90% |
| Provider Registry | 集中式 Provider 元數據 | 新增 Provider 一處修改、自動傳播 |
| Channel Plugin | 泛型頻道抽象 | 新增頻道只需實現接口 |
| 安全內容包裝 | 邊界標記 + 注入偵測 | 防 prompt injection |
| Agent 分解 | RunContext + ToolExecutor + ContextBuilder | 職責清晰、精簡 40% |
| **Sandbox** | **路徑驗證 + Symlink 防護** | **防文件系統逃逸** |
| **Tool Approval** | **三級授權 (once/session/deny)** | **安全與體驗的平衡** |
| **Controller Pattern** | **Observer 模式取代 Hooks** | **UI 框架解耦、可測試** |

這二十個模式可以組合使用，構建一個高效、可維護、安全的 AI Agent 應用。

---

**文檔版本**: 6.0
**基於 Dexter 版本**: 2026.2.21
**更新日期**: 2026-02-23
