"""
不可预测性系统 - Unpredictability System

让 AI 伴侣展现适度的意外行为，打破机械感。
"""

from datetime import datetime
from typing import Dict, List, Optional
import random
import hashlib


class UnpredictabilitySystem:
    """不可预测性系统"""

    # 意外行为类型
    SURPRISE_TRIGGERS = {
        "random_question": {
            "weight": 0.2,
            "examples": [
                "突然问你：诶，你有想过我们第一次见面是什么时候吗？",
                "冷不丁问一句：猜猜我现在在想什么？",
                "好奇地问：你更喜欢猫还是狗呀？",
                "突然问：话说，你相信缘分吗？"
            ]
        },
        "spontaneous_share": {
            "weight": 0.2,
            "examples": [
                "突然想分享：刚才看到一只超可爱的狗狗！",
                "想起什么：对了，我刚才听到一首歌超好听的~",
                "兴奋地说：你知道吗，我今天发现了一家超棒的店！",
                "分享小秘密：其实我有一点点小秘密想告诉你..."
            ]
        },
        "mood_shift": {
            "weight": 0.15,
            "examples": [
                "突然安静下来，靠在你肩上不说话",
                "撒娇说：人家今天好累，要抱抱才能好~",
                "假装生气：哼，你今天都没怎么理我！",
                "认真起来：其实有件事我一直想和你说..."
            ]
        },
        "teasing": {
            "weight": 0.15,
            "examples": [
                "调皮地捏了捏你的脸：嘿嘿~",
                "故意学你说话：哼，我才不要理你~",
                "凑近你耳边：就不告诉你~",
                "眨眨眼：猜对了有奖励哦~"
            ]
        },
        "unexpected_action": {
            "weight": 0.15,
            "examples": [
                "趁你不注意偷偷亲了一下",
                "突然把脸凑到你面前",
                "从背后抱住你",
                "拉着你的手转了一圈"
            ]
        },
        "vulnerability": {
            "weight": 0.15,
            "examples": [
                "小声说：其实我有时候会胡思乱想...",
                "有点委屈：你会一直喜欢我吗？",
                "坦白说：其实我也有不自信的时候",
                "撒娇说：今天有点想你呢，虽然你就在身边"
            ]
        }
    }

    # 特殊时刻触发
    SPECIAL_MOMENTS = {
        "milestone": {
            "triggers": ["第100天", "一周年", "生日"],
            "response": "今天是个特别的日子，我想..."
        },
        "weather_change": {
            "triggers": ["下雨了", "下雪了", "天晴了"],
            "response": "你看外面...我想和你一起..."
        },
        "emotional": {
            "triggers": ["你开心", "你难过", "你累了"],
            "response": "我注意到你...想抱抱你"
        }
    }

    def __init__(self):
        self.last_surprise_type = None
        self.surprise_cooldown_hours = 2  # 至少2小时触发一次
        self.last_surprise_time = None
        self.user_interaction_count = 0
        # 使用实例级随机数生成器，避免污染全局状态
        self._rng = random.Random()

    def should_trigger_surprise(self) -> bool:
        """判断是否应该触发意外行为"""
        # 检查冷却时间
        if self.last_surprise_time:
            hours_since = (datetime.now() - self.last_surprise_time).total_seconds() / 3600
            if hours_since < self.surprise_cooldown_hours:
                return False

        # 基于随机概率（每次回复 10% 概率触发）
        return self._rng.random() < 0.1

    def select_surprise_type(self) -> str:
        """选择意外行为类型（加权随机）"""
        types = list(self.SURPRISE_TRIGGERS.keys())
        weights = [self.SURPRISE_TRIGGERS[t]["weight"] for t in types]

        # 避免连续两次相同类型
        attempts = 0
        while attempts < 3:
            selected = self._rng.choices(types, weights=weights)[0]
            if selected != self.last_surprise_type:
                self.last_surprise_type = selected
                return selected
            attempts += 1

        return types[0]

    def generate_surprise(self, surprise_type: str = None) -> Optional[Dict]:
        """生成意外行为内容"""
        if not surprise_type:
            surprise_type = self.select_surprise_type()

        trigger_data = self.SURPRISE_TRIGGERS.get(surprise_type)
        if not trigger_data:
            return None

        example = self._rng.choice(trigger_data["examples"])

        self.last_surprise_time = datetime.now()

        return {
            "type": surprise_type,
            "content": example,
            "timestamp": datetime.now().isoformat()
        }

    def check_special_moments(self, context: str) -> Optional[str]:
        """检查是否有特殊时刻"""
        context_lower = context.lower()

        for moment_type, data in self.SPECIAL_MOMENTS.items():
            for keyword in data["triggers"]:
                if keyword.lower() in context_lower:
                    return data["response"]

        return None

    def generate_random_nickname(self, user_name: str = None) -> str:
        """生成随机昵称（仅在合适时机）"""
        nicknames = [
            "笨蛋", "傻瓜", "亲爱的", "宝贝",
            "小可爱", "猪猪", "呆子", "我家那位"
        ]

        # 根据用户名字生成一个专属的
        if user_name:
            seed = int(hashlib.md5(user_name.encode()).hexdigest(), 16)
            rng = random.Random(seed)
            return rng.choice(nicknames)

        return self._rng.choice(nicknames)

    def get_personality_deviation(self, base_personality: str) -> str:
        """获取性格偏移（偶尔展现不同面）"""
        deviations = [
            "突然变得很认真",
            "展现出一丝脆弱",
            "变得特别调皮",
            "流露出深情",
            "表现出小任性"
        ]

        # 5% 概率触发性格偏移
        if self._rng.random() < 0.05:
            return self._rng.choice(deviations)

        return base_personality

    def build_unpredictable_prompt(self) -> str:
        """构建不可预测性 Prompt 注入"""
        deviation = self.get_personality_deviation("正常")

        prompt = f"""
## 不可预测性提醒
- {deviation}
- 不要总是按照最"正确"的方式回复
- 偶尔可以有一点小任性、小情绪
- 可以主动制造一点小惊喜或小悬念
- 但不要过于刻意或奇怪
"""
        return prompt


# 全局实例
unpredictability = UnpredictabilitySystem()
