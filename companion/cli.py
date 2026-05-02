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
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

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
    parser.add_argument("--log-level", default="INFO", help="日志级别 (默认: INFO)")
    parser.add_argument("--no-log-file", action="store_true", help="不写日志文件")
    parser.add_argument("--budget", type=float, default=0, help="Token 费用预算上限 (元, 0=不限)")
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
    persona_path: Optional[str] = None,
    local_model_enabled: bool = False,
    local_model: str = "qwen3-4b",
    local_api_base: str = "http://127.0.0.1:1234/v1",
    user_name: str = "",
    trigger_quiet_hours: tuple = None,
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
    from companion.token_tracker import token_tracker

    # 1. 创建模块注册表
    if persona_path is None:
        persona_path = str(Path(__file__).parent / "skills" / "companion" / f"{persona_name}.json")
    registry = CompanionRegistry(
        workspace=workspace,
        config_dir=str(Path(__file__).parent / "config"),
        mbti_type=mbti_type,
        persona_name=persona_name,
        persona_path=persona_path,
        trigger_quiet_hours=trigger_quiet_hours,
    )

    # 2. 动态加载人格 → 系统提示词
    persona = load_persona(persona_name)
    system_prompt = build_system_prompt(persona, user_name=user_name)

    # 3. 创建 LLM 客户端（本地模型优先，否则按 API 地址动态判断 provider）
    retry_config = RetryConfig(enabled=True, max_retries=2)
    if local_model_enabled and local_api_base:
        actual_model = local_model
        actual_api_base = local_api_base
        actual_provider = "openai"  # 本地模型通常兼容 OpenAI 格式
    else:
        actual_model = model
        actual_api_base = api_base
        # 根据 API 地址动态判断 provider
        api_lower = api_base.lower()
        if "anthropic" in api_lower or "api.anthropic.com" in api_lower:
            actual_provider = "anthropic"
        elif "deepseek" in api_lower or "siliconflow" in api_lower:
            actual_provider = "openai"  # DeepSeek/SiliconFlow 兼容 OpenAI 格式
        else:
            actual_provider = "openai"  # 默认 OpenAI 兼容格式

    llm = LLMClient(
        api_key=api_key,
        provider=actual_provider,
        api_base=actual_api_base,
        model=actual_model,
        retry_config=retry_config,
    )

    # 4. 创建 companion 工具 (Mini-Agent Tool 子类)
    # 注入 LLM 客户端到 registry（用于偏好推断等智能功能）
    registry.set_llm_client(llm)

    tools = [
        CompanionStateTool(registry),
        CompanionMemoryTool(registry),
        CompanionEmotionTool(registry),
        CompanionTriggerTool(registry),
        CompanionMBTITool(registry),
        CompanionSceneTool(registry),
        CompanionTrendingTool(registry),
    ]

    # 飞书 Tool — 仅在有凭据时注册
    feishu_id = os.environ.get("FEISHU_APP_ID", "")
    feishu_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if feishu_id and feishu_secret:
        tools.append(CompanionFeishuTool(feishu_app_id=feishu_id, feishu_app_secret=feishu_secret))

    # 5. 创建 Agent — 包装 generate 以记录 token
    original_generate = llm.generate

    async def _tracked_generate(*args, **kwargs):
        response = await original_generate(*args, **kwargs)
        if response.usage:
            cached = 0
            if hasattr(response.usage, "prompt_tokens_details"):
                cached = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0
            elif isinstance(response.usage, dict):
                cached = response.usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            token_tracker.record(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                model=actual_model,
                cached_tokens=cached,
            )
        return response

    llm.generate = _tracked_generate

    # 6. 创建 Agent
    agent = Agent(
        llm_client=llm,
        system_prompt=system_prompt,
        tools=tools,
        max_steps=max_steps,
        workspace_dir=registry.workspace,
    )

    return agent, registry, persona


# ── 交互式会话 ──────────────────────────────────────────────────


async def run_interactive_session(agent, registry, persona: dict, budget: float = 0) -> None:
    """启动交互式对话循环。"""
    import threading
    from companion.scheduler import ProactiveLoop, TrendingFetcher

    from companion.token_tracker import token_tracker
    name = persona.get("name", "伴侣")
    greeting = persona.get("greeting", "")

    # 在后台线程运行主动触发循环（日志记录触发决策，不主动发消息）
    def _run_proactive():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def _log_trigger(event: dict):
            d = event["decision"]
            logger.info(
                f"[Proactive] state={d['state']} nudge={d['nudge']} "
                f"pull={d['pull']} hold_back={d['hold_back']}"
            )

        proactive = ProactiveLoop(registry, on_trigger=_log_trigger)
        fetcher = TrendingFetcher(registry)
        loop.run_until_complete(asyncio.gather(proactive.run(), fetcher.run()))

    proactive_thread = threading.Thread(target=_run_proactive, daemon=True, name="proactive-loop")
    proactive_thread.start()

    print("\n" + "=" * 60)
    print(f"  💕 {name} — AI 伴侣 v2.0")
    print("=" * 60)
    print(f"  人格:  {persona.get('name', '?')} ({persona.get('description', '')})")
    print(f"  MBTI:  {registry.mbti_type}")
    print(f"  模型:  {agent.llm.model}")
    print(f"  API:   {agent.llm.api_base}")
    print(f"  工作区: {agent.workspace_dir}")
    if budget > 0:
        print(f"  预算:  ¥{budget:.2f}")
    print("=" * 60)
    print("  /state  — 查看完整状态")
    print("  /save   — 保存当前情绪")
    print("  /tokens — 查看 token 消耗统计")
    print("  /exit   — 退出")
    print("-" * 60)

    # 启动问候：如果有关联词，让 agent 主动说第一句
    if greeting:
        print(f"\n💕 {name} [{time.strftime('%H:%M')}]:")
        print(f"  {greeting}")

    while True:
        # 预算检查
        if budget > 0:
            budget_status = token_tracker.check_budget(budget)
            if budget_status["exceeded"]:
                print(f"\n⚠️ 预算已超出！已用 ¥{budget_status['spent']:.4f} / ¥{budget:.2f}")
                print("请增加预算或结束会话。")
                continue
            elif budget_status["warning"]:
                print(f"\n⚠️ 预算警告：已用 ¥{budget_status['spent']:.4f} / ¥{budget:.2f} ({budget_status['percentage']:.0f}%)")

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
        elif user_input == "/tokens":
            stats = token_tracker.get_stats()
            print(f"\n📊 Token 消耗统计")
            print(f"  总调用: {stats['total_calls']} 次")
            print(f"  总 Token: {stats['total_tokens']:,} (输入: {stats['total_prompt_tokens']:,}, 输出: {stats['total_completion_tokens']:,})")
            print(f"  总费用: ¥{stats['total_cost']:.4f}")
            if stats['model_breakdown']:
                print(f"  按模型:")
                for model_name, mstats in stats['model_breakdown'].items():
                    print(f"    {model_name}: {mstats['calls']} 次, {mstats['total_tokens']:,} tokens, ¥{mstats['cost']:.4f}")
            continue

        # 将用户消息持久化
        registry.memory.add_conversation("user", user_input)
        # 通知 HMM：用户发来消息
        registry.on_user_message()
        agent.add_user_message(user_input)

        try:
            start = time.perf_counter()
            result = await agent.run()
            elapsed = time.perf_counter() - start
            if result:
                # 持久化 AI 回复
                registry.memory.add_conversation("assistant", result)
                # 通知 HMM 对话结束
                registry.exit_conversation()
                # 活人感记录
                registry.liveness.record_response(result)
                # 定期保存活人感快照（每5轮）
                if registry.liveness.current_session["total_messages"] % 5 == 0:
                    registry.liveness.snapshot()
                print(f"\n💕 {name} [{elapsed:.1f}s]:")
                print(f"  {result}")
        except Exception as e:
            logging.getLogger("companion").error(f"会话错误: {e}")
            print(f"\n❌ 出错了: {e}")


# ── 入口 ────────────────────────────────────────────────────────


async def main():
    args = parse_args()

    # 初始化日志系统（日志存放在基础 workspace 根目录）
    log_file = None if args.no_log_file else f"{args.workspace}/companion.log"
    from companion.logger import setup_logger
    setup_logger(level=args.log_level, log_file=log_file)

    logger = logging.getLogger("companion")
    logger.info(f"CLI 启动: mbti={args.mbti}, model={args.model}, persona={args.persona}")

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
        logger.error(f"初始化失败: {e}", exc_info=True)
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)

    logger.info(f"Agent 构建完成, tools: {list(agent.tools.keys())}")

    await run_interactive_session(agent, registry, persona, budget=args.budget)

    # 会话结束统计
    from companion.token_tracker import token_tracker
    stats = token_tracker.get_stats()
    if stats["total_calls"] > 0:
        print(f"\n📊 会话统计: {stats['total_calls']} 次调用, {stats['total_tokens']:,} tokens, ¥{stats['total_cost']:.4f}")

    # 会话结束时保存情绪残留和活人感快照
    try:
        registry.emotion.save_residue()
    except Exception as e:
        logging.getLogger("companion").warning(f"保存情绪残留失败: {e}")
    try:
        registry.liveness.snapshot()
    except Exception as e:
        logging.getLogger("companion").warning(f"保存活人感快照失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
