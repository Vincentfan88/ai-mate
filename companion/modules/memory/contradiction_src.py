"""
矛盾检测 - Contradiction Detection

检测 LLM 生成内容与 Fact Store 中已存储事实之间的矛盾。
用于防止角色"自创没发生过的事"。

两种模式：
1. 快速检测（基于关键词，无需 LLM）：集成在 FactStore._quick_contradiction_check()
2. 深度检测（基于 LLM）：本模块，提供修正建议
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.memory.fact_store import Contradiction, FactStore

logger = logging.getLogger(__name__)


# -------------------- 检测 Prompt --------------------

CONTRADICTION_CHECK_PROMPT = """你是一个逻辑一致性检验员。

给定角色已知的事实和一条新的回复，检测是否存在矛盾。

已知事实：
{facts_context}

新回复：
{new_response}

角色立场：{char_name}（{char_personality}）

检测规则：
1. 事实与回复直接矛盾（明确否定了之前说过的话）
2. 事实与回复隐含矛盾（回复暗示了与事实相反的状态）
3. 角色行为与已知性格标签矛盾
4. 回复中创造了新事实但该事实与已知事实冲突

如果不矛盾，输出：
{{"has_contradiction": false}}

如果矛盾，输出：
{{"has_contradiction": true, "contradiction_type": "...", "description": "...", "suggested_fix": "..."}}

矛盾类型：
- "fact_negation"：直接否定已有事实
- "implied_negation"：暗示否定
- "personality_drift"：性格漂移
- "self_invention"：自创与已有矛盾的事实

修正建议应该让角色以自然的方式承认矛盾或给出解释，而不是直接说"我忘了"。"""


# -------------------- 矛盾检测结果 --------------------

@dataclass
class ContradictionResult:
    """矛盾检测结果"""
    has_contradiction: bool
    contradiction_type: Optional[str] = None   # fact_negation / implied_negation / personality_drift / self_invention
    description: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence: float = 0.0                      # 0.0-1.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def __bool__(self) -> bool:
        return self.has_contradiction


# -------------------- ContradictionDetector --------------------

class ContradictionDetector:
    """
    矛盾检测器

    检测 LLM 生成内容与 Fact Store 之间的矛盾，
    并提供修正建议。
    """

    def __init__(
        self,
        fact_store: FactStore,
        persona_name: str = "小美",
        personality_tags: Optional[List[str]] = None,
    ):
        self._fact_store = fact_store
        self._persona_name = persona_name
        self._personality_tags = personality_tags or []

    def check(
        self,
        new_response: str,
        llm_client: Any = None,
        use_llm: bool = True,
    ) -> ContradictionResult:
        """
        检测新回复是否与 Fact Store 矛盾

        Args:
            new_response: LLM 新生成的回复
            llm_client: LLM 客户端（用于深度检测）
            use_llm: 是否使用 LLM 深度检测（False=只用快速检测）

        Returns:
            ContradictionResult
        """
        # 1. 快速检测（基于关键词，无需 LLM）
        quick_result = self._quick_check(new_response)
        if quick_result.has_contradiction:
            return quick_result

        if not use_llm or not llm_client:
            return ContradictionResult(has_contradiction=False)

        # 2. LLM 深度检测
        return self._llm_check(new_response, llm_client)

    def _quick_check(self, response: str) -> ContradictionResult:
        """快速矛盾检测（基于关键词和 Fact Store 已有事实）"""
        response_lower = response.lower()
        existing_facts = self._fact_store.get_all_facts_for_check()

        for fact in existing_facts:
            if fact.subject != "assistant":
                continue  # 快速检测只检查角色事实

            fact_lower = fact.content.lower()

            # 检测直接否定
            negation_indicators = [
                ("不", "不" in response_lower and "不是" not in response_lower),
                ("没", "没" in response_lower),
                ("从不", "从不" in response_lower),
                ("从不会", "从不会" in response_lower),
                ("从来没有", "从来没有" in response_lower),
            ]

            for keyword, negated in negation_indicators:
                if not negated:
                    continue

                # 检测事实中的关键词是否被否定
                for fact_keyword in fact.content:
                    if len(fact_keyword) < 2:
                        continue
                    # 事实包含该关键词，且回复中出现了否定词
                    if fact_keyword in fact.content and keyword in response_lower:
                        # 检查是否真的在否定这个事实
                        for neg_word in ["不", "没", "从不"]:
                            if f"{neg_word}{fact_keyword[0]}" in response or f"不{fact_keyword[:2]}" in response:
                                return ContradictionResult(
                                    has_contradiction=True,
                                    contradiction_type="fact_negation",
                                    description=f"回复似乎否定了已知事实：{fact.content}",
                                    suggested_fix=f"承认之前的说法并给出解释，如：'之前我确实说过……但这次情况不太一样'",
                                    confidence=0.7,
                                )

            # 检测性格漂移（简单版）
            for trait in self._personality_tags:
                if trait in response_lower:
                    # 如果回复明显表现出与性格标签相反的行为
                    opposite_traits = {
                        "傲娇": ["直接承认", "坦诚"],
                        "冷漠": ["热情地", "主动关心"],
                        "温柔": ["冷淡地", "粗暴地"],
                    }
                    opposites = opposite_traits.get(trait, [])
                    if any(opp in response_lower for opp in opposites):
                        return ContradictionResult(
                            has_contradiction=True,
                            contradiction_type="personality_drift",
                            description=f"回复表现出与性格标签'{trait}'相反的行为",
                            suggested_fix=f"保持傲娇/冷漠/温柔的角色特点，用符合性格的方式表达",
                            confidence=0.5,
                        )

        return ContradictionResult(has_contradiction=False)

    def _llm_check(
        self,
        response: str,
        llm_client: Any,
    ) -> ContradictionResult:
        """使用 LLM 进行深度矛盾检测"""
        facts_context = self._fact_store.get_fact_context(max_facts=20)
        if not facts_context:
            return ContradictionResult(has_contradiction=False, confidence=0.0)

        personality_str = "、".join(self._personality_tags) if self._personality_tags else "未定义"

        prompt = CONTRADICTION_CHECK_PROMPT.format(
            facts_context=facts_context,
            new_response=response,
            char_name=self._persona_name,
            char_personality=personality_str,
        )

        try:
            import json as _json

            raw_response = llm_client.chat([{"role": "user", "content": prompt}])

            # 尝试从响应中提取 JSON
            response_text = raw_response.strip()
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()

            result_dict = _json.loads(response_text)

            return ContradictionResult(
                has_contradiction=result_dict.get("has_contradiction", False),
                contradiction_type=result_dict.get("contradiction_type"),
                description=result_dict.get("description"),
                suggested_fix=result_dict.get("suggested_fix"),
                confidence=0.85,
            )

        except (_json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning(f"[ContradictionDetector] LLM 检测解析失败: {e}")
            return ContradictionResult(has_contradiction=False, confidence=0.0)

    def check_and_record(
        self,
        new_response: str,
        turn_id: int,
        llm_client: Any = None,
    ) -> ContradictionResult:
        """
        检测矛盾并自动记录

        Returns:
            ContradictionResult（包含已记录的 contradiction_id）
        """
        result = self.check(new_response, llm_client)

        if result.has_contradiction:
            # 找到涉及的事实（简化：通过描述匹配）
            existing_facts = self._fact_store.get_all_facts_for_check()
            matched_fact = None
            for fact in existing_facts:
                if result.description and fact.content[:20] in result.description:
                    matched_fact = fact
                    break

            if matched_fact:
                # 记录矛盾
                from core.memory.fact_store import Contradiction
                self._fact_store._record_contradiction(
                    matched_fact,
                    Fact(
                        id=f"generated_{turn_id}",
                        content=new_response[:100],
                        subject="assistant",
                        source_type="assistant",
                        importance=0.5,
                    ),
                    description=result.description or "检测到矛盾",
                )

        return result


# -------------------- 修正 Prompt Builder --------------------

class FixPromptBuilder:
    """
    根据矛盾检测结果生成修正 prompt
    """

    @staticmethod
    def build_fact_reminder(fact_store: FactStore) -> str:
        """生成事实提醒 prompt"""
        context = fact_store.get_fact_context(max_facts=10)
        if not context:
            return ""

        return f"""
【事实锚定提醒】
角色需要忠于已知事实。如果新回复与以下事实不符，请调整回复方式：

{context}

注意：不要直接说"我忘了"，而是用符合角色的方式解释或承认。
"""

    @staticmethod
    def build_fix_prompt(
        contradiction_result: ContradictionResult,
        char_name: str,
        char_personality: str,
    ) -> str:
        """生成修正 prompt（用于要求 LLM 重写）"""
        if not contradiction_result.has_contradiction:
            return ""

        fix = contradiction_result.suggested_fix or "调整回复以避免矛盾"

        return f"""
【回复修正】
上一条回复被检测出矛盾（{contradiction_result.description}）。
修正要求：{fix}

请以角色"{char_name}"（性格：{char_personality}）的口吻，重新生成一条不矛盾的回复。
"""
