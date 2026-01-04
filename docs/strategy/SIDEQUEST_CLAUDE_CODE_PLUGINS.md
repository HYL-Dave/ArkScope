# 支線任務：Claude Code 插件評估

> **創建日期**: 2026-01-04
> **狀態**: 評估中
> **相關**: 工作流優化，未來專案效率提升

---

## 1. 背景

Claude Code 支援插件系統，可以擴展功能。本文檔評估哪些官方插件對本專案（及未來專案）有幫助。

---

## 2. 插件系統概述

### 2.1 運作方式

```
1. 添加 Marketplace (插件目錄)
2. 從 Marketplace 安裝個別插件
3. 插件提供: Slash Commands / Subagents / Skills / Hooks / MCP / LSP
```

### 2.2 安裝範圍

| 範圍 | 檔案位置 | 用途 |
|------|----------|------|
| User | 全局設定 | 所有專案可用 |
| Project | `.claude/settings.json` | 團隊共享 |
| Local | `.claude/settings.local.json` | 個人本地 (gitignore) |

---

## 3. 官方插件清單與評估

### 3.1 程式語言 LSP 插件 (Code Intelligence)

| 插件名稱 | 語言 | 需要安裝 | 對本專案用處 | 建議 |
|----------|------|----------|--------------|------|
| `pyright-lsp` | Python | `pip install pyright-langserver` | ⭐⭐⭐⭐⭐ 高 | **強烈推薦** |
| `typescript-lsp` | TypeScript | `npm i -g typescript-language-server` | ⭐ 低 | 不需要 |
| `rust-analyzer-lsp` | Rust | `rustup component add rust-analyzer` | ⭐ 低 | 不需要 |
| `gopls-lsp` | Go | `go install golang.org/x/tools/gopls` | ⭐ 低 | 不需要 |
| `jdtls-lsp` | Java | Eclipse JDT LS | ⭐ 低 | 不需要 |

**Python LSP 能提供**:
- 更準確的 Go to Definition
- Find References
- Hover 文檔
- 型別檢查錯誤
- 自動完成建議

### 3.2 外部整合插件 (MCP Servers)

| 插件名稱 | 整合服務 | 對本專案用處 | 建議 |
|----------|----------|--------------|------|
| `github` | GitHub | ⭐⭐⭐⭐ 高 | **推薦** (PR, Issues) |
| `gitlab` | GitLab | ⭐ 低 | 不使用 GitLab |
| `atlassian` | Jira/Confluence | ⭐⭐ 中 | 如果用 Jira 追蹤 |
| `notion` | Notion | ⭐⭐ 中 | 如果用 Notion 記錄 |
| `slack` | Slack | ⭐⭐ 中 | 團隊溝通整合 |
| `linear` | Linear | ⭐⭐ 中 | 專案管理替代 |
| `asana` | Asana | ⭐ 低 | 不使用 |
| `figma` | Figma | ⭐ 低 | 無設計需求 |
| `vercel` | Vercel | ⭐ 低 | 無前端部署 |
| `firebase` | Firebase | ⭐ 低 | 不使用 |
| `supabase` | Supabase | ⭐ 低 | 不使用 |
| `sentry` | Sentry | ⭐⭐⭐ 中高 | 如果部署後監控 |

### 3.3 開發工作流插件

| 插件名稱 | 功能 | 對本專案用處 | 建議 |
|----------|------|--------------|------|
| `commit-commands` | Git 工作流 (commit, push, PR) | ⭐⭐⭐⭐ 高 | **推薦** |
| `pr-review-toolkit` | PR 審查 agents | ⭐⭐⭐ 中高 | 推薦 |
| `agent-sdk-dev` | Agent SDK 開發 | ⭐⭐ 中 | 已安裝 |
| `plugin-dev` | 插件開發工具 | ⭐⭐ 中 | 想自訂插件時 |

### 3.4 輸出風格插件

| 插件名稱 | 功能 | 對本專案用處 | 建議 |
|----------|------|--------------|------|
| `explanatory-output-style` | 教育性解釋輸出 | ⭐⭐ 中 | 學習新概念時 |
| `learning-output-style` | 互動學習模式 | ⭐⭐ 中 | 學習新概念時 |

---

## 4. 本專案推薦安裝

### 4.1 第一優先級 (強烈推薦)

```bash
# 1. Python LSP - 提升程式碼理解能力
pip install pyright
/plugin install pyright-lsp@claude-plugins-official

# 2. GitHub 整合 - PR/Issue 工作流
/plugin install github@claude-plugins-official

# 3. Commit 工作流
/plugin install commit-commands@claude-plugins-official
```

### 4.2 第二優先級 (推薦嘗試)

```bash
# PR 審查工具
/plugin install pr-review-toolkit@claude-plugins-official

# 如果使用 Sentry 監控
/plugin install sentry@claude-plugins-official
```

### 4.3 可選 (視需求)

```bash
# 如果用 Jira 追蹤任務
/plugin install atlassian@claude-plugins-official

# 如果用 Notion 記錄
/plugin install notion@claude-plugins-official
```

---

## 5. 已安裝插件清單

當前專案已安裝:

| 插件 | 來源 | 功能 |
|------|------|------|
| `feature-dev:feature-dev` | claude-code-plugins | 功能開發引導 |
| `agent-sdk-dev:new-sdk-app` | claude-code-plugins | Agent SDK 設定 |

---

## 6. 測試計劃

### 6.1 Python LSP 測試

**安裝步驟**:
```bash
pip install pyright
/plugin install pyright-lsp@claude-plugins-official --scope project
```

**測試項目**:
- [ ] Go to Definition 是否更準確
- [ ] Find References 是否能找到所有引用
- [ ] Hover 是否顯示型別資訊
- [ ] 錯誤偵測是否有效

**測試檔案**:
- `env_stocktrading_llm.py` (複雜環境類)
- `score_sentiment_openai.py` (多函數檔案)
- `data_sources/base.py` (抽象類)

### 6.2 GitHub 插件測試

**測試項目**:
- [ ] 能否直接查看 Issue
- [ ] 能否創建 PR
- [ ] 能否查看 PR 評論

### 6.3 Commit Commands 測試

**測試項目**:
- [ ] `/commit` 指令是否好用
- [ ] 自動生成的 commit message 品質
- [ ] PR 創建流程是否流暢

---

## 7. 追蹤清單

- [ ] **S-01-01**: 安裝 pyright LSP
- [ ] **S-01-02**: 測試 Python LSP 效果
- [ ] **S-01-03**: 安裝 GitHub 插件
- [ ] **S-01-04**: 測試 GitHub 整合
- [ ] **S-01-05**: 安裝 commit-commands
- [ ] **S-01-06**: 測試 commit 工作流
- [ ] **S-01-07**: 記錄測試結果反饋
- [ ] **S-01-08**: 決定最終採用的插件組合

---

## 8. 插件管理指令參考

```bash
# 查看已安裝
/plugin

# 安裝插件
/plugin install <name>@<marketplace>

# 安裝到專案 (團隊共享)
/plugin install <name>@<marketplace> --scope project

# 禁用/啟用
/plugin disable <name>@<marketplace>
/plugin enable <name>@<marketplace>

# 移除
/plugin uninstall <name>@<marketplace>

# 添加第三方 marketplace
/plugin marketplace add <source>

# 更新 marketplace
/plugin marketplace update <name>
```

---

## 9. 資源連結

| 資源 | URL |
|------|-----|
| 插件文檔 | https://docs.anthropic.com/en/docs/claude-code/plugins |
| 發現插件 | https://docs.anthropic.com/en/docs/claude-code/discover-plugins |
| Marketplace 文檔 | https://docs.anthropic.com/en/docs/claude-code/plugin-marketplaces |
| 插件參考 | https://docs.anthropic.com/en/docs/claude-code/plugins-reference |

---

*創建者: Claude Code*
*最後更新: 2026-01-04*