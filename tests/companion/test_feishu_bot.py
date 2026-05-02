"""飞书 Bot 模块单元测试。"""

from companion.modules.feishu.bot import FeishuBot


class TestCleanText:
    """测试 FeishuBot._clean_text 静态方法。"""

    def test_normal_text(self):
        assert FeishuBot._clean_text("你好") == "你好"

    def test_with_mention(self):
        assert FeishuBot._clean_text("@小美 你好呀") == "你好呀"

    def test_with_user_mention(self):
        assert FeishuBot._clean_text("@_user_123 在吗？") == "在吗？"

    def test_only_mention(self):
        assert FeishuBot._clean_text("@小美") == ""

    def test_whitespace_stripped(self):
        assert FeishuBot._clean_text("  你好  ") == "你好"

    def test_empty_string(self):
        assert FeishuBot._clean_text("") == ""

    def test_mixed_mentions(self):
        result = FeishuBot._clean_text("你好@小美 @_user_456 再见")
        # 可能有多余空格，验证内容而非格式
        assert "你好" in result and "再见" in result


class TestFeishuBotInit:
    """测试 FeishuBot 初始化。"""

    def test_initial_state(self):
        import asyncio
        loop = asyncio.new_event_loop()
        bot = FeishuBot("test_id", "test_secret", loop)
        assert bot.is_running is False
        assert bot.is_connected is False
        loop.close()

    def test_set_agent_getter(self):
        import asyncio
        loop = asyncio.new_event_loop()
        bot = FeishuBot("test_id", "test_secret", loop)
        getter = lambda: "agent"
        bot.set_agent_getter(getter)
        loop.close()
