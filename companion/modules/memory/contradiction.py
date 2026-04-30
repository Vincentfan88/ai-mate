"""矛盾检测模块 — 两阶段：关键词匹配 → LLM语义判断。"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# LLM 深度检测 Prompt
CONTRADICTION_CHECK_PROMPT = """你是一个逻辑一致性检验员。

检测新回复与已知事实之间是否存在矛盾。

已知事实：
{known_facts}

新回复：
{new_response}

检测规则：
1. 事实与回复直接矛盾（明确否定了之前说过的话）
2. 事实与回复隐含矛盾（回复暗示了与事实相反的状态）
3. 回复中创造了新事实但该事实与已知事实冲突

如果不矛盾，输出：
{{"has_contradiction": false}}

如果矛盾，输出：
{{"has_contradiction": true, "contradiction_type": "...", "description": "...", "severity": "high/medium/low"}}

矛盾类型：
- "fact_negation"：直接否定已有事实
- "implied_negation"：暗示否定
- "self_invention"：自创与已知矛盾的事实

 severity：high（明确矛盾）、medium（可能矛盾）、low（轻微不一致）
"""


class ContradictionDetector:
    """矛盾检测 — 两阶段：关键词匹配 → LLM语义判断"""

    def __init__(self):
        self.contradiction_pairs = [
            ("喜欢", "讨厌"),
            ("爱", "不爱"),
            ("经常", "很少"),
            ("总是", "从不"),
            ("想要", "不想"),
            ("觉得好", "觉得不好"),
            ("开心", "不开心"),
            ("忙", "闲"),
            ("累", "不累"),
            ("压力大", "没压力"),
        ]

    def detect(
        self,
        facts: List[dict],
        new_response: str = None,
        llm_client: Any = None,
    ) -> List[dict]:
        """
        检测矛盾

        Args:
            facts: 已知事实列表
            new_response: 新回复（可选，用于 Stage 2 LLM 检测）
            llm_client: LLM 客户端（可选）

        Returns:
            矛盾列表
        """
        # Stage 1: 关键词匹配
        contradictions = self._keyword_detect(facts)

        # Stage 2: LLM 语义判断（如果有新回复和 LLM 客户端）
        if new_response and llm_client and facts:
            llm_result = self._llm_detect(facts, new_response, llm_client)
            if llm_result and llm_result.get("has_contradiction"):
                # 避免与 Stage 1 重复
                already_found = self._is_duplicate(llm_result, contradictions)
                if not already_found:
                    contradictions.append(llm_result)

        return contradictions

    def _keyword_detect(self, facts: List[dict]) -> List[dict]:
        """Stage 1: 基于关键词的矛盾检测"""
        contradictions = []

        for i, f1 in enumerate(facts):
            for f2 in facts[i + 1:]:
                pair = self._check_contradiction(f1, f2)
                if pair:
                    contradictions.append(pair)

        return contradictions

    def _check_contradiction(self, f1: dict, f2: dict) -> Optional[dict]:
        """检查两条事实是否矛盾"""
        c1 = f1.get("content", "")
        c2 = f2.get("content", "")

        for kw1, kw2 in self.contradiction_pairs:
            if kw1 in c1 and kw2 in c2:
                return {
                    "fact1": f1,
                    "fact2": f2,
                    "conflict_keywords": (kw1, kw2),
                    "severity": "medium",
                    "stage": "keyword",
                }
            if kw2 in c1 and kw1 in c2:
                return {
                    "fact1": f1,
                    "fact2": f2,
                    "conflict_keywords": (kw2, kw1),
                    "severity": "medium",
                    "stage": "keyword",
                }

        return None

    def _llm_detect(
        self,
        facts: List[dict],
        new_response: str,
        llm_client: Any,
    ) -> Optional[dict]:
        """Stage 2: LLM 语义矛盾检测"""
        facts_str = "\n".join(f"- {f.get('content', '')}" for f in facts)

        prompt = CONTRADICTION_CHECK_PROMPT.format(
            known_facts=facts_str,
            new_response=new_response,
        )

        try:
            raw = llm_client.chat([{"role": "user", "content": prompt}])
            return self._parse_llm_response(raw, facts, new_response)
        except Exception as e:
            logger.warning(f"[ContradictionDetector] LLM 检测失败: {e}")
            return None

    def _parse_llm_response(
        self,
        response: str,
        facts: List[dict],
        new_response: str,
    ) -> Optional[dict]:
        """解析 LLM 返回的矛盾检测结果"""
        text = response.strip()

        # 提取 JSON（处理 markdown code block）
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            result = json.loads(text)
            if not result.get("has_contradiction"):
                return None

            return {
                "fact1": {"content": "LLM detected"},
                "fact2": {"content": new_response[:100]},
                "conflict_keywords": None,
                "severity": result.get("severity", "medium"),
                "contradiction_type": result.get("contradiction_type", "unknown"),
                "description": result.get("description", ""),
                "stage": "llm",
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[ContradictionDetector] LLM 响应解析失败: {e}")
            return None

    def _is_duplicate(self, llm_result: dict, existing: List[dict]) -> bool:
        """检查 LLM 结果是否与已有的关键词检测重复"""
        for c in existing:
            desc = llm_result.get("description", "")
            if desc and any(
                kw in desc for kw in c.get("conflict_keywords", ()) if kw
            ):
                return True
        return False

    def should_follow_up(self, contradictions: List[dict]) -> bool:
        """判断是否需要追问"""
        return len(contradictions) > 0
