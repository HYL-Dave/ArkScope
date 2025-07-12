"""
LLMScorer 2.0
--------------
• 一次回傳 sentiment、risk 以及 reasoning_steps（Chain-of-Thought）
• 透過 OpenAI Function Calling + Structured Outputs
• 保留多金鑰輪替、Flex、fallback 純文字解析
最後更新：2025-07-12
"""

import openai, tiktoken, pandas as pd, json, re, time, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Tuple, Optional

class LLMScorer:
    # ─────────────────────── 初始化 ─────────────────────── #
    def __init__(self, config: dict):
        """
        config 需包含：
          · openai_api_key 或 openai_api_keys (list)
        選填：
          · daily_token_limit, allow_flex, flex_timeout, flex_retries
          · model (預設 gpt-4.1-mini), temperature, max_tokens
          · capture_reasoning (bool, 預設 True)
        """
        self.logger = logging.getLogger(__name__)

        # -------- API Key 與輪替 -------- #
        self.api_keys: List[str] = config.get("openai_api_keys") or \
                                   [config.get("openai_api_key")]
        if not self.api_keys or not all(self.api_keys):
            raise ValueError("須提供 openai_api_key 或 openai_api_keys")

        self.current_idx = 0
        openai.api_key = self.api_keys[self.current_idx]

        self.daily_token_limit = config.get("daily_token_limit")
        self.tokens_used = {k: 0 for k in self.api_keys}

        self.allow_flex = config.get("allow_flex", False)
        self.flex_timeout = config.get("flex_timeout", 900)
        self.flex_retries = config.get("flex_retries", 1)
        self.use_flex_mode = False
        self.stop_after_limit = False

        # -------- 模型與請求參數 -------- #
        self.model_cfg = {
            "model": config.get("model", "gpt-4.1-mini"),
            "temperature": config.get("temperature", 0),
            "max_tokens": config.get("max_tokens", 5)
        }
        self.capture_reasoning = config.get("capture_reasoning", True)

        # -------- 定價表（每 1 K token）-------- #
        self.pricing = {
            "gpt-4.1":      {"input": 0.002,   "output": 0.008},
            "gpt-4.1-mini": {"input": 0.0004,  "output": 0.0016},
            "gpt-4.1-nano": {"input": 0.0001,  "output": 0.0004},
            "o4-mini":      {"input": 0.0011,  "output": 0.0044},
            "o3":           {"input": 0.002,   "output": 0.008},
            "gpt-4o-mini":  {"input": 0.00015, "output": 0.0006}
        }

        # -------- Tokenizer -------- #
        self.tokenizers = self._init_tokenizers()

        # -------- 成本追蹤 -------- #
        self.cost = {
            "input_tokens": 0,
            "output_tokens": 0,
            "requests": 0,
            "usd": 0.0
        }

        # -------- Prompt 模板 -------- #
        self.prompts = self._load_prompts()

        # -------- Function-Call Schema -------- #
        self.score_schema = [{
            "type": "function",
            "function": {
                "name": "score_article",
                "description": "Return reasoning steps and sentiment & risk scores (1-5)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning_steps": {
                            "type": "array",
                            "items": { "type": "string" },
                            "description": "Step-by-step reasoning"
                        },
                        "sentiment": {
                            "type": "integer",
                            "enum": [1,2,3,4,5]
                        },
                        "risk": {
                            "type": "integer",
                            "enum": [1,2,3,4,5]
                        }
                    },
                    "required": ["reasoning_steps", "sentiment", "risk"]
                }
            }
        }]

    # ─────────────────────── 私有工具 ─────────────────────── #
    def _init_tokenizers(self):
        tk = {}
        for name in self.pricing.keys():
            try:
                # 嘗試直接獲取模型的 tokenizer
                tk[name] = tiktoken.encoding_for_model(name)
            except Exception:
                # 如果失敗，使用相近模型的 tokenizer
                if "4.1" in name or "o3" in name or "o4" in name:
                    # 使用 GPT-4 的 tokenizer 作為替代
                    try:
                        tk[name] = tiktoken.encoding_for_model("gpt-4")
                    except:
                        pass
        tk["default"] = tiktoken.get_encoding("cl100k_base")
        return tk

    def _load_prompts(self):
        return {
            "system": (
                "You are a financial analyst expert in sentiment and risk grading "
                "for stock market news."
            ),
            "user": (
                "Article:\n{article}\n\n"
                "Given the above article about {symbol}, "
                "think step-by-step then output JSON via the defined schema."
            )
        }

    def _estimate_tokens(self, txt: str, model: str) -> int:
        enc = self.tokenizers.get(model) or self.tokenizers["default"]
        try: return len(enc.encode(txt))
        except Exception: return len(txt) // 4

    def _rotate_key(self, used: int):
        if self.daily_token_limit is None: return
        cur = self.api_keys[self.current_idx]
        self.tokens_used[cur] += used
        if self.tokens_used[cur] < self.daily_token_limit: return

        if self.allow_flex:
            self.logger.warning(f"{cur} 達上限，改用 Flex")
            self.use_flex_mode = True
            return
        self.logger.warning(f"{cur} 達上限，輪替金鑰並停止批次")
        self.current_idx = (self.current_idx + 1) % len(self.api_keys)
        openai.api_key = self.api_keys[self.current_idx]
        self.stop_after_limit = True

    def _cost(self, model: str, in_tok: int, out_tok: int) -> float:
        rate = self.pricing.get(model, self.pricing["gpt-4.1-nano"])
        return (in_tok/1000)*rate["input"] + (out_tok/1000)*rate["output"]

    # ─────────────────────── 單篇評分 ─────────────────────── #
    def _score_via_function(self, article: str, symbol: str
                            ) -> Tuple[int,int,List[str]]:
        prompt = [
            {"role": "system", "content": self.prompts["system"]},
            {"role": "user", "content": self.prompts["user"].format(
                article=article, symbol=symbol)}
        ]
        model = self.model_cfg["model"]

        # 基本參數
        params = {
            "model": model,
            "messages": prompt,
            "tools": self.score_schema,
            "tool_choice": "auto",
            "max_tokens": 60,            # reasoning + JSON
            "temperature": self.model_cfg["temperature"]
        }

        # o-系列專用參數
        if model.startswith("o"):
            params["reasoning_effort"] = "high"

        # Flex
        if self.use_flex_mode:
            params["service_tier"] = "flex"
            params["timeout"] = self.flex_timeout

        # 執行請求
        attempt, max_try = 0, (self.flex_retries if self.use_flex_mode else 3)
        while attempt < max_try:
            attempt += 1
            try:
                resp = openai.chat.completions.create(**params)
                usage = resp.usage
                in_tok, out_tok = usage.prompt_tokens, usage.completion_tokens
                self._rotate_key(usage.total_tokens)
                self.cost["input_tokens"]  += in_tok
                self.cost["output_tokens"] += out_tok
                self.cost["requests"]     += 1
                self.cost["usd"]          += self._cost(model, in_tok, out_tok)

                # ─── 解析 tool_call ─── #
                if resp.choices[0].message.tool_calls:
                    args = json.loads(
                        resp.choices[0].message.tool_calls[0].function.arguments)
                    return args["sentiment"], args["risk"], args["reasoning_steps"]

                # 若沒命中 tool_call，fallback
                text = resp.choices[0].message.content.strip()
                return *self._parse_text_scores(text), []
            except (openai.RateLimitError, openai.APITimeoutError):
                wait = 30 * attempt
                self.logger.warning(f"API 受限，{wait}s 後重試")
                time.sleep(wait)
            except Exception as e:
                self.logger.error(f"API 失敗 {e}; 重試 {attempt}/{max_try}")
                time.sleep(1*attempt)
        return 3,3,[]

    # 備援解析器
    def _parse_text_scores(self, txt: str) -> Tuple[int,int]:
        nums = re.findall(r'\b[1-5]\b', txt)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        # heuristics
        return 3,3

    # ─────────────────────── 對外 API ─────────────────────── #
    def score_single(self, article: str, symbol: str
                     ) -> Tuple[int,int,List[str]]:
        # 長文截斷
        if len(article) > 3000: article = article[:3000] + "…"
        return self._score_via_function(article, symbol)

    def batch_score(self, df: pd.DataFrame, workers: int = 5) -> pd.DataFrame:
        if not {"Article", "Stock_symbol"} <= set(df.columns):
            raise ValueError("DataFrame 需含 Article 與 Stock_symbol 欄位")
        df = df.copy()
        df[["sentiment_u","risk_q"]] = None
        if self.capture_reasoning:
            df["reasoning_steps"] = None
        df["timestamp"] = datetime.now().isoformat()

        with ThreadPoolExecutor(max_workers=workers) as ex:
            fut = {
                ex.submit(self.score_single, row.Article, row.Stock_symbol): i
                for i,row in df.iterrows()
                if pd.notna(row.Article) and str(row.Article).strip()
            }
            for f in as_completed(fut):
                i = fut[f]
                try:
                    s,r,rs = f.result()
                    df.at[i,"sentiment_u"] = s
                    df.at[i,"risk_q"] = r
                    if self.capture_reasoning: df.at[i,"reasoning_steps"] = rs
                except Exception as e:
                    self.logger.error(f"索引 {i} 失敗: {e}")
                    df.at[i,["sentiment_u","risk_q"]] = 3
                if self.stop_after_limit:
                    self.logger.warning("達每日限額，提前結束")
                    break
        return df

    # ─────────────────────── 成本報告 ─────────────────────── #
    def cost_summary(self) -> Dict:
        req = max(self.cost["requests"], 1)
        return {
            "model": self.model_cfg["model"],
            "requests": self.cost["requests"],
            "input_tokens": self.cost["input_tokens"],
            "output_tokens": self.cost["output_tokens"],
            "est_cost_usd": round(self.cost["usd"],4),
            "avg_per_request": round(self.cost["usd"]/req,4)
        }

# ──────────────── CLI 測試 ──────────────── #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = {
        "openai_api_keys": ["sk-..."],
        "daily_token_limit": 100000,
        "allow_flex": True,
        "model": "gpt-4.1-mini",
        "capture_reasoning": True
    }
    scorer = LLMScorer(cfg)
    sample = pd.DataFrame({
        "Article": [
            "Apple shares soar after record iPhone sales and stronger-than-expected guidance.",
            "Tesla faces regulatory inquiry over autopilot safety, sparking investor concerns."
        ],
        "Stock_symbol": ["AAPL", "TSLA"]
    })
    out = scorer.batch_score(sample, workers=2)
    print(out[["sentiment_u","risk_q","reasoning_steps"]])
    print(scorer.cost_summary())
