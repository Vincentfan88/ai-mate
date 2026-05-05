"""Agent 包装器 — 隐藏 Mini-Agent 的内部输出，只保留最终回复。"""
import io
import logging
import contextlib
from datetime import datetime

from companion.token_tracker import token_tracker

logger = logging.getLogger("companion")


class SilentAgentWrapper:
    """包装 Agent，抑制 thinking/tool_call 等内部输出。

    使用方式:
        wrapper = SilentAgentWrapper(agent, registry)
        result = await wrapper.run(message)  # 无干扰输出
    """

    def __init__(self, agent, registry=None):
        self._agent = agent
        self._registry = registry
        # 注入 token 记录器到 LLM 客户端
        self._patch_llm()

    def _patch_llm(self):
        """Monkey-patch LLM generate 以记录 token 消耗。"""
        original_generate = self._agent.llm.generate
        model = self._agent.llm.model

        async def _tracked_generate(*args, **kwargs):
            response = await original_generate(*args, **kwargs)
            if response.usage:
                cached = 0
                if hasattr(response.usage, "prompt_tokens_details"):
                    cached = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0
                elif hasattr(response.usage, "cache_read_input_tokens"):
                    cached = getattr(response.usage, "cache_read_input_tokens", 0) or 0

                token_tracker.record(
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                    model=model,
                    cached_tokens=cached,
                )
            return response

        self._agent.llm.generate = _tracked_generate

    @property
    def agent(self):
        return self._agent

    @property
    def registry(self):
        return self._registry

    async def run(self, user_message: str) -> str:
        """发送用户消息并获取最终回复，自动记录对话日志。"""
        # 记录用户消息到对话日志
        if self._registry:
            self._registry.memory.add_conversation("user", user_message)

        self._agent.add_user_message(user_message)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = await self._agent.run()

        if not result:
            logger.warning(f"[AgentWrapper] agent.run() returned {result!r}")
            return "(empty response)"

        if result.startswith("LLM call failed") or result.startswith("Task couldn't be completed"):
            logger.warning(f"[AgentWrapper] agent error: {result[:80]}")
            return "(empty response)"

        # 记录 AI 回复到对话日志
        if self._registry:
            self._registry.memory.add_conversation("assistant", result)
            # 更新 HMM 状态（状态转移）
            try:
                self._registry.exit_conversation()
            except Exception as e:
                logging.getLogger("companion").warning(f"HMM update failed: {e}")

            # 活人感记录：从 AI 回复中分析维度数据
            try:
                self._registry.liveness.record_response(result)
            except Exception as e:
                logging.getLogger("companion").warning(f"Liveness recording failed: {e}")

        return result
