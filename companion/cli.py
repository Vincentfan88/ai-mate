#!/usr/bin/env python3
"""AI 伴侣 CLI — 端到端交互入口。

通过 Mini-Agent 框架将 companion 模块整合为一个可对话的 AI 伴侣。

使用方式:
    python -m companion.cli
    python -m companion.cli --mbti INTJ --persona default
    python -m companion.cli --model deepseek-v4-flash

默认通过 cc-switch 本地代理 (http://127.0.0.1:15721) 连接 LLM。
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# ── 解析命令行参数 ──────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 伴侣 CLI")
    parser.add_argument("--mbti", default="ENFP", help="伴侣 MBTI 类型 (默认: ENFP)")
    parser.add_argument("--model", default="deepseek-v4-flash", help="LLM 模型名 (默认: deepseek-v4-flash)")
    parser.add_argument("--api-base", default="http://127.0.0.1:15721", help="API 地址 (默认: cc-switch 代理)")
    parser.add_argument("--api-key", default="cc-switch-proxy", help="API Key (cc-switch 代理接受任意值)")
    parser.add_argument("--workspace", default="workspace/companion", help="运行时数据目录")
    parser.add_argument("--persona", default="default", help="人格配置文件名 (companion/skills/companion/{name}.json)")
    parser.add_argument("--max-steps", type=int, default=5, help="每轮最大执行步数")
    return parser.parse_args()


# ── agent 构建工厂 ──────────────────────────────────────────────


def build_companion_agent(
    mbti_type: str = "ENFP",
    persona_name: str = "default",
    workspace: str = "workspace/companion",
    api_base: str = "http://127.0.0.1:15721",
    api_key: str = "cc-switch-proxy",
    model: str = "deepseek-v4-flash",
    max_steps: int = 5,
):
    """构建一个完整配置的 AI 伴侣 Agent 实例。

    返回 (agent, registry, persona_name) 元组。
    """
    from mini_agent import LLMClient
    from mini_agent.agent import Agent
    from mini_agent.retry import RetryConfig

    from companion.modules.registry import CompanionRegistry
    from companion.agent import (
        CompanionStateTool,
        CompanionMemoryTool,
        CompanionEmotionTool,
        CompanionTriggerTool,
        CompanionMBTITool,
        CompanionFeishuTool,
        CompanionSceneTool,
        CompanionTrendingTool,
    )
    from companion.agent.persona import load_persona, build_system_prompt

    # 1. 创建模块注册表
    registry = CompanionRegistry(
        workspace=workspace,
        config_dir=str(Path(__file__).parent / "config"),
        mbti_type=mbti_type,
    )

    # 2. 动态加载人格 → 系统提示词
    persona = load_persona(persona_name)
    system_prompt = build_system_prompt(persona)

    # 3. 创建 LLM 客户端 (通过 cc-switch 代理)
    retry_config = RetryConfig(enabled=True, max_retries=2)
    llm = LLMClient(
        api_key=api_key,
        provider="anthropic",
        api_base=api_base,
        model=model,
        retry_config=retry_config,
    )

    # 4. 创建 companion 工具 (Mini-Agent Tool 子类)
    tools = [
        CompanionStateTool(registry),
        CompanionMemoryTool(registry),
        CompanionEmotionTool(registry),
        CompanionTriggerTool(registry),
        CompanionMBTITool(registry),
        CompanionFeishuTool(),
        CompanionSceneTool(registry),
        CompanionTrendingTool(registry),
    ]

    # 5. 创建 Agent
    agent = Agent(
        llm_client=llm,
        system_prompt=system_prompt,
        tools=tools,
        max_steps=max_steps,
        workspace_dir=workspace,
    )

    return agent, registry, persona


# ── 交互式会话 ──────────────────────────────────────────────────


async def run_interactive_session(agent, registry, persona: dict) -> None:
    """启动交互式对话循环。"""
    name = persona.get("name", "伴侣")
    greeting = persona.get("greeting", "")

    print("\n" + "=" * 60)
    print(f"  💕 {name} — AI 伴侣 v2.0")
    print("=" * 60)
    print(f"  人格:  {persona.get('name', '?')} ({persona.get('description', '')})")
    print(f"  MBTI:  {registry.mbti_type}")
    print(f"  模型:  {agent.llm.model}")
    print(f"  API:   {agent.llm.api_base}")
    print(f"  工作区: {agent.workspace_dir}")
    print("=" * 60)
    print("  /state  — 查看完整状态")
    print("  /save   — 保存当前情绪")
    print("  /exit   — 退出")
    print("-" * 60)

    # 启动问候：如果有关联词，让 agent 主动说第一句
    if greeting:
        print(f"\n💕 {name} [{time.strftime('%H:%M')}]:")
        print(f"  {greeting}")

    while True:
        try:
            user_input = input(f"\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{name}: 嗯~ 舍不得你走... 明天一定要找我哦 💕")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print(f"{name}: 嗯~ 舍不得你走... 明天一定要找我哦 💕")
            break
        elif user_input == "/state":
            from companion.modules.extras import TimeContext
            emotion = registry.emotion.get_current_emotion("time_passage")
            hmm_state = registry.trigger.hmm.current_state if hasattr(registry.trigger, "hmm") else "unknown"
            stage = registry.relationship.get_current_stage()
            print(f"\n📊 当前状态")
            print(f"  情绪: {emotion['emotion']} ({emotion['intensity']})")
            print(f"  HMM:  {hmm_state}")
            print(f"  关系: {stage.name_cn} Lv.{stage.level}")
            continue
        elif user_input == "/save":
            registry.emotion.save_residue()
            print("✅ 情绪残留已保存")
            continue

        # 将用户消息持久化
        registry.memory.add_conversation("user", user_input)
        agent.add_user_message(user_input)

        try:
            start = time.perf_counter()
            result = await agent.run()
            elapsed = time.perf_counter() - start
            if result:
                # 持久化 AI 回复
                registry.memory.add_conversation("assistant", result)
                print(f"\n💕 {name} [{elapsed:.1f}s]:")
                print(f"  {result}")
        except Exception as e:
            print(f"\n❌ 出错了: {e}")


# ── 入口 ────────────────────────────────────────────────────────


async def main():
    args = parse_args()

    try:
        agent, registry, persona = build_companion_agent(
            mbti_type=args.mbti,
            persona_name=args.persona,
            workspace=args.workspace,
            api_base=args.api_base,
            api_key=args.api_key,
            model=args.model,
            max_steps=args.max_steps,
        )
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)

    await run_interactive_session(agent, registry, persona)

    # 会话结束时保存情绪残留
    try:
        registry.emotion.save_residue()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
