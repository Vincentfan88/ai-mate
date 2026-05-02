"""Token 消耗统计 — 累计每次 LLM 调用的 token 和费用。

用法：
    from companion.token_tracker import token_tracker, record_token_usage

    # 在 LLM 调用后记录
    if response.usage:
        token_tracker.record(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            model=agent.llm.model,
        )

    # 查看统计
    stats = token_tracker.get_stats()
    print(f"总消耗: {stats['total_cost']:.4f} 元")
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 模型价格表（元/百万 token）— 根据实际使用的模型更新
# 默认使用 DeepSeek 价格作为参考
MODEL_PRICES: Dict[str, dict] = {
    # DeepSeek
    "deepseek-v4-flash": {"input": 1.0, "output": 4.0},   # 元/百万 token
    "deepseek-v3": {"input": 2.0, "output": 8.0},
    "deepseek-r1": {"input": 4.0, "output": 16.0},
    # Claude
    "claude-sonnet-4-6-20250514": {"input": 12.0, "output": 60.0},
    "claude-haiku-4-5-20251001": {"input": 2.5, "output": 12.5},
    # OpenAI
    "gpt-4o": {"input": 18.0, "output": 54.0},
    "gpt-4o-mini": {"input": 1.1, "output": 4.4},
    # 默认（未知模型，按 DeepSeek-v3 计费）
    "default": {"input": 2.0, "output": 8.0},
}


class TokenEntry:
    """单次 token 消耗记录。"""

    def __init__(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        model: str,
        timestamp: str,
    ):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model = model
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "timestamp": self.timestamp,
        }


class TokenTracker:
    """Token 消耗追踪器。"""

    def __init__(self, workspace: str = "workspace/companion"):
        self.workspace = Path(workspace)
        self.stats_file = self.workspace / "token_stats.json"
        self._entries: List[TokenEntry] = []
        self._load_stats()

    def _load_stats(self) -> None:
        """加载历史统计。"""
        if self.stats_file.exists():
            try:
                data = json.loads(self.stats_file.read_text(encoding="utf-8"))
                self._entries = [TokenEntry(**e) for e in data.get("entries", [])]
            except Exception as e:
                logger.warning(f"[TokenTracker] 加载统计失败: {e}")

    def _save_stats(self) -> None:
        """持久化统计。"""
        self.workspace.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "entries": [e.to_dict() for e in self._entries],
                "last_updated": datetime.now().isoformat(),
            }
            self.stats_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[TokenTracker] 保存统计失败: {e}")

    def record(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        timestamp: Optional[str] = None,
    ) -> TokenEntry:
        """记录一次 LLM 调用的 token 消耗。

        Args:
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            model: 模型名称
            timestamp: 时间戳，默认当前时间
        """
        entry = TokenEntry(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            timestamp=timestamp or datetime.now().isoformat(),
        )
        self._entries.append(entry)
        self._save_stats()

        price = self._get_model_price(model)
        cost = self._calculate_entry_cost(entry, price)
        logger.info(
            f"Token: {entry.total_tokens} tokens "
            f"(input: {prompt_tokens}, output: {completion_tokens}) "
            f"model: {model}, cost: ¥{cost:.4f}"
        )
        return entry

    def get_stats(self, since: Optional[str] = None) -> dict:
        """获取统计信息。

        Args:
            since: ISO 格式时间戳，只统计此时间之后的数据

        Returns:
            统计信息字典
        """
        entries = self._entries
        if since:
            entries = [e for e in entries if e.timestamp >= since]

        if not entries:
            return {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_tokens_per_call": 0,
                "model_breakdown": {},
            }

        total_prompt = sum(e.prompt_tokens for e in entries)
        total_completion = sum(e.completion_tokens for e in entries)
        total_tokens = total_prompt + total_completion

        # 按模型分组统计
        model_breakdown: Dict[str, dict] = {}
        for e in entries:
            if e.model not in model_breakdown:
                price = self._get_model_price(e.model)
                model_breakdown[e.model] = {
                    "calls": 0,
                    "total_tokens": 0,
                    "price": price,
                    "cost": 0.0,
                }
            mb = model_breakdown[e.model]
            mb["calls"] += 1
            mb["total_tokens"] += e.total_tokens
            mb["cost"] += self._calculate_entry_cost(e, mb["price"])

        total_cost = sum(mb["cost"] for mb in model_breakdown.values())

        return {
            "total_calls": len(entries),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_tokens_per_call": total_tokens // len(entries),
            "model_breakdown": model_breakdown,
        }

    def check_budget(self, budget: float) -> dict:
        """检查是否超出预算。

        Args:
            budget: 预算上限（元）

        Returns:
            包含预算状态、已用金额、剩余金额的字典
        """
        stats = self.get_stats()
        remaining = budget - stats["total_cost"]
        return {
            "budget": budget,
            "spent": stats["total_cost"],
            "remaining": remaining,
            "percentage": (stats["total_cost"] / budget * 100) if budget > 0 else 0,
            "exceeded": remaining < 0,
            "warning": 0.8 < (stats["total_cost"] / budget) < 1.0 if budget > 0 else False,
        }

    def reset(self) -> None:
        """清空所有统计。"""
        self._entries.clear()
        self._save_stats()
        logger.info("[TokenTracker] 统计已重置")

    def _get_model_price(self, model: str) -> dict:
        """获取模型价格。"""
        for key, price in MODEL_PRICES.items():
            if key in model.lower():
                return price
        return MODEL_PRICES["default"]

    def _calculate_entry_cost(self, entry: TokenEntry, price: dict) -> float:
        """计算单次调用费用（元）。"""
        input_cost = (entry.prompt_tokens / 1_000_000) * price["input"]
        output_cost = (entry.completion_tokens / 1_000_000) * price["output"]
        return input_cost + output_cost


# 全局单例
token_tracker = TokenTracker()
