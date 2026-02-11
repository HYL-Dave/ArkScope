# Anthropic SDK Streaming 踩坑經驗

> 日期: 2026-02-12

## 問題

使用 Anthropic Python SDK (v0.79.0) 搭配 Claude Opus 4.6 + thinking 模式時，
`max_tokens` 設為 128,000（模型最大 output），CLI 查詢直接報錯：

```
Error: Streaming is required for operations that may take longer than 10 minutes.
```

## 根本原因

這是 **SDK client 端的 ValueError**，不是 server timeout。

位於 `anthropic/_base_client.py:726`：

```python
def _calculate_nonstreaming_timeout(self, max_tokens, max_nonstreaming_tokens):
    maximum_time = 60 * 60      # 1 hour
    default_time = 60 * 10      # 10 minutes

    expected_time = maximum_time * max_tokens / 128_000
    if expected_time > default_time:
        raise ValueError("Streaming is required...")
```

**Threshold**: `max_tokens > 128000 * 600 / 3600 = 21,333`

任何 `max_tokens > 21,333` 的 non-streaming 請求都會被 SDK 拒絕。

## 為什麼我們設這麼高

設計決策：code gen 和 thinking 模式都給模型最大 output 空間。

- reasoning/thinking tokens 從 `max_tokens` 中扣，空間不足會截斷推理
- 按實際用量計費，設高不多花錢
- 業界標準做法（Aider, Cursor, Codex CLI 都用 model max）

但我們忽略了 SDK 有 client-side 上限檢查。

## 修復

將 `client.messages.create()` 改為 `client.messages.stream()` + `stream.get_final_message()`：

```python
# Before (ValueError when max_tokens > 21333):
response = client.messages.create(
    model=model, max_tokens=128000, messages=messages, **kwargs
)

# After (no limit):
with client.messages.stream(
    model=model, max_tokens=128000, messages=messages, **kwargs
) as stream:
    response = stream.get_final_message()
```

`get_final_message()` 回傳的 `Message` 物件與 `create()` 完全相同
（`.content`, `.stop_reason`, `.usage` 等欄位都一樣），downstream 零影響。

## 影響範圍

三處都需要修改：
1. `src/agents/cli.py` — CLI 互動查詢（用戶直接遇到的）
2. `src/agents/anthropic_agent/agent.py` — agent 模組的 tool loop
3. `src/tools/code_generator.py` — code gen 的 Anthropic 呼叫

## 測試 mock 更新

原本 mock `client.messages.create.return_value`，改為 mock streaming context manager：

```python
def _make_stream_cm(response):
    """Mock: with client.messages.stream(...) as s: s.get_final_message() -> response"""
    stream = MagicMock()
    stream.get_final_message.return_value = response
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=stream)
    cm.__exit__ = MagicMock(return_value=False)
    return cm

# Usage:
client.messages.stream.return_value = _make_stream_cm(mock_response)
# Multiple calls:
client.messages.stream.side_effect = [_make_stream_cm(r1), _make_stream_cm(r2)]
# Check call args:
call_kwargs = client.messages.stream.call_args
```

## 教訓

1. **SDK 的 client-side validation 容易被忽略** — 不只有 server 會拒絕請求
2. **streaming 幾乎沒有缺點** — 回傳物件相同，且未來可以做 incremental display
3. **先查本地 SDK 源碼** — `inspect.getsource()` + grep 是最快的除錯方式
4. **設定 model max output 是對的** — 但要配合正確的 transport 層（streaming）