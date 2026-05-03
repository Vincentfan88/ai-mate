"""Agent 包装器 — 隐藏 Mini-Agent 的内部输出，只保留最终回复。"""
import io
import logging
import contextlib

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
            # 记录详细原因便于排查
            if result is None:
                logger.warning("[AgentWrapper] agent.run() returned None")
            else:
                logger.warning(f"[AgentWrapper] agent.run() returned empty string")
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
