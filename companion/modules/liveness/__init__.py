"""活人感八维度计算模块 — 从真实互动数据中推导维度值。"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import random
from pathlib import Path


@dataclass
class LivenessScore:
    """活人感指标快照"""
    timestamp: str
    dimension_scores: Dict[str, float]
    overall_score: float
    sample_count: int


class LivenessTracker:
    """活人感八维度追踪器 — 从消息/互动中计算真实维度值。"""

    DIMENSION_KEYS = [
        "主动性", "一致性", "成长性", "情绪化",
        "脆弱性", "身体存在感", "不可预测性", "依恋度"
    ]

    # 不可预测性：随机昵称
    NICKNAMES = [
        "笨蛋", "傻瓜", "亲爱的", "宝贝",
        "小可爱", "猪猪", "呆子", "我家那位"
    ]

    # 不可预测性：惊喜模式检测
    SURPRISE_PATTERNS = [
        "猜猜", "冷不丁", "突然问", "其实我", "话说", "对了，",
        "咦", "诶", "哎呀", "哇塞", "突然想起",
    ]

    def __init__(self, data_path: str = "workspace/companion/liveness.json"):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.metrics_history: List[LivenessScore] = []
        self.current_session: Dict = {
            "initiated_contacts": 0,
            "total_contacts": 0,
            "emotions_expressed": [],
            "vulnerability_count": 0,
            "physical_references": 0,
            "unpredictable_responses": 0,
            "user_references": 0,
            "total_messages": 0,
            "contradictions_detected": 0,
            "inferences_made": 0,
            "impulsive_triggers": 0,
            "surprise_triggered": False,
            "nickname_used": "",
        }
        self.learned_topics: List[str] = []
        self._load_history()

    @property
    def week_start(self) -> datetime:
        """本周一日期 — 动态计算，不依赖构造时间"""
        now = datetime.now()
        return now - timedelta(days=now.weekday())

    def _load_history(self):
        """加载历史指标"""
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text())
                self.metrics_history = [
                    LivenessScore(**m) for m in data.get("history", [])
                ]
            except Exception:
                pass

    def _save_history(self):
        """保存历史指标"""
        try:
            data = {
                "history": [
                    {"timestamp": m.timestamp, "dimension_scores": m.dimension_scores,
                     "overall_score": m.overall_score, "sample_count": m.sample_count}
                    for m in self.metrics_history[-100:]
                ]
            }
            self.data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            pass

    # -------------------- 记录方法 --------------------

    def record_initiated_contact(self):
        """记录主动联系"""
        self.current_session["initiated_contacts"] += 1
        self.current_session["total_contacts"] += 1

    def record_response(self, content: str, context: dict = None):
        """记录一次回复，分析各维度（含不可预测性检测）"""
        self.current_session["total_messages"] += 1
        self.current_session["total_contacts"] += 1
        text = content

        # 情绪表达
        emotions = self._detect_emotions(text)
        self.current_session["emotions_expressed"].extend(emotions)

        # 身体存在感
        physical_words = [
            "抱", "靠", "坐", "躺", "站", "走", "手", "脸", "眼", "头", "肩",
            "呼吸", "心跳", "温度", "靠在你", "靠过来", "伸手", "握住",
        ]
        if any(w in text for w in physical_words):
            self.current_session["physical_references"] += 1

        # 用户引用
        user_words = ["你", "亲爱的", "宝贝", "傻瓜", "笨蛋"]
        if any(w in text for w in user_words):
            self.current_session["user_references"] += 1

        # 脆弱性表达
        vuln_words = [
            "有点累", "想你了", "不太舒服", "撒娇", "委屈", "孤单",
            "寂寞", "无聊", "睡不着", "难过", "心累", "困", "有点难过",
            "今天不开心", "心情不好", "有点失落",
        ]
        if any(w in text for w in vuln_words):
            self.current_session["vulnerability_count"] += 1

        # 不可预测性：显式词汇
        unpredict_markers = ["咦", "啊", "诶", "哇", "哎呀", "嗯？", "哈？",
                             "真的吗", "等等", "话说", "其实", "对了", "突然"]
        if any(m in text for m in unpredict_markers):
            self.current_session["unpredictable_responses"] += 1

        # 不可预测性：惊喜行为模式
        if any(m in content for m in self.SURPRISE_PATTERNS):
            self.current_session["surprise_triggered"] = True

    def record_surprise(self):
        """记录一次惊喜/意外行为（来自外部触发）"""
        self.current_session["surprise_triggered"] = True
        self.current_session["unpredictable_responses"] += 1

    def generate_nickname(self, user_name: str = None) -> str:
        """生成随机昵称（供调用方使用，同时计入不可预测性）"""
        import hashlib
        if user_name:
            seed = int(hashlib.md5(user_name.encode()).hexdigest(), 16)
            rng = random.Random(seed)
            chosen = rng.choice(self.NICKNAMES)
        else:
            chosen = random.choice(self.NICKNAMES)
        self.current_session["nickname_used"] = chosen
        return chosen

    def record_contradiction(self, found: bool = True):
        """记录矛盾检测"""
        if found:
            self.current_session["contradictions_detected"] += 1

    def record_inference(self):
        """记录推断"""
        self.current_session["inferences_made"] += 1

    def record_impulsive_trigger(self):
        """记录冲动触发"""
        self.current_session["impulsive_triggers"] += 1

    def learn_topic(self, topic: str):
        """学习新话题"""
        if topic not in self.learned_topics:
            self.learned_topics.append(topic)

    def _detect_emotions(self, text: str) -> List[str]:
        """检测文本中的情绪"""
        emotion_map = {
            "开心": ["开心", "高兴", "快乐", "太好了", "哈哈", "嘻嘻", "笑死"],
            "担心": ["担心", "怕", "紧张", "怕你"],
            "想念": ["想", "思念", "好久不见", "想你", "念你"],
            "撒娇": ["嗯~", "嘛~", "好不好嘛", "哼", "啦", "哟"],
            "害羞": ["害羞", "脸红", "不好意思", "羞"],
            "难过": ["难过", "伤心", "委屈", "不舒服", "失落"],
            "生气": ["生气", "气", "讨厌", "哼"],
            "兴奋": ["兴奋", "太棒了", "哇塞", "好激动"],
        }
        detected = []
        for emotion, keywords in emotion_map.items():
            if any(kw in text for kw in keywords):
                detected.append(emotion)
        return detected

    # -------------------- 得分计算 --------------------

    def calculate_scores(self) -> Dict[str, float]:
        """计算当前各维度得分"""
        s = self.current_session

        # 1. 主动性：主动发起 / 总互动
        total = max(s["total_contacts"], 1)
        initiative = s["initiated_contacts"] / total

        # 2. 一致性：基于矛盾检测，每次矛盾扣分
        contradictions = s.get("contradictions_detected", 0)
        consistency = max(0.0, 1.0 - contradictions * 0.05)

        # 3. 成长性：基于学到的话题和推断
        growth = self._calculate_growth()

        # 4. 情绪化：基于检测到的情绪种类
        unique_emotions = len(set(s["emotions_expressed"]))
        emotional = min(1.0, unique_emotions / 5)  # 5 种以上满分

        # 5. 脆弱性：sigmoid 曲线，2-3 次/周最佳
        days_this_week = max(0.001, (datetime.now() - self.week_start).total_seconds() / 86400)
        vuln_rate = s["vulnerability_count"] / days_this_week
        vulnerability = min(1.0, vuln_rate / (vuln_rate + 2.5))

        # 6. 身体存在感
        total_msgs = max(s["total_messages"], 1)
        physical = min(1.0, s["physical_references"] / total_msgs * 3)

        # 7. 不可预测性：综合显式标记 + 惊喜行为 + 昵称
        unpredictability = self._calculate_unpredictability()

        # 8. 依恋度：用户引用频率，30-50% 最佳
        attachment_rate = s["user_references"] / total_msgs
        if 0.3 <= attachment_rate <= 0.5:
            attachment = 0.9 + (attachment_rate - 0.3) * 0.5
        elif attachment_rate > 0.5:
            attachment = max(0.7, 1.0 - (attachment_rate - 0.5) * 0.6)
        else:
            attachment = max(0.3, attachment_rate * 2)

        return {
            "主动性": round(initiative, 2),
            "一致性": round(consistency, 2),
            "成长性": round(growth, 2),
            "情绪化": round(emotional, 2),
            "脆弱性": round(vulnerability, 2),
            "身体存在感": round(physical, 2),
            "不可预测性": round(unpredictability, 2),
            "依恋度": round(attachment, 2),
        }

    def _calculate_growth(self) -> float:
        """计算成长性：话题学习 + 推断确认率"""
        topics = len(self.learned_topics)
        inferences = self.current_session.get("inferences_made", 0)

        # 基线
        if topics == 0 and inferences == 0:
            return 0.5

        # 话题越多越好，10 个话题 = 满分
        topic_score = min(1.0, 0.3 + topics * 0.07)
        # 推断也有贡献
        inference_score = min(1.0, 0.3 + inferences * 0.1)

        return round(topic_score * 0.7 + inference_score * 0.3, 2)

    def _calculate_unpredictability(self) -> float:
        """计算不可预测性 — 整合惊喜/昵称/意外行为"""
        s = self.current_session
        total_msgs = max(s["total_messages"], 1)

        # 显式不可预测表达比例
        explicit = s.get("unpredictable_responses", 0)
        explicit_score = min(1.0, explicit / total_msgs * 8)

        # 冲动触发
        impulsive = s.get("impulsive_triggers", 0)
        if impulsive == 0:
            impulse_score = 0.5
        else:
            ratio = total_msgs / impulsive
            impulse_score = 0.8 if 5 <= ratio <= 20 else 0.6

        # 惊喜行为加分
        surprise_bonus = 0.15 if s.get("surprise_triggered", False) else 0.0

        # 昵称使用加分
        nickname_bonus = 0.05 if s.get("nickname_used") else 0.0

        # 综合：显式标记 50% + 冲动 30% + 基础分 20% + 惊喜/昵称加分
        base_score = 0.3  # 基础不可预测性下限
        unpredictability = (
            explicit_score * 0.5
            + impulse_score * 0.3
            + base_score * 0.2
            + surprise_bonus
            + nickname_bonus
        )
        return round(min(1.0, max(0.2, unpredictability)), 2)

    def get_overall_score(self, scores: dict = None) -> float:
        """计算综合得分"""
        if scores is None:
            scores = self.calculate_scores()

        weights = {
            "主动性": 0.15, "一致性": 0.15, "成长性": 0.10,
            "情绪化": 0.12, "脆弱性": 0.10, "身体存在感": 0.10,
            "不可预测性": 0.13, "依恋度": 0.15,
        }
        overall = sum(scores.get(k, 0) * w for k, w in weights.items())
        return round(overall, 2)

    def snapshot(self) -> LivenessScore:
        """保存快照"""
        scores = self.calculate_scores()
        overall = self.get_overall_score(scores)
        metric = LivenessScore(
            timestamp=datetime.now().isoformat(),
            dimension_scores=scores,
            overall_score=overall,
            sample_count=self.current_session["total_messages"],
        )
        self.metrics_history.append(metric)
        self._save_history()
        return metric

    def get_trend(self, dimension: str, last_n: int = 7) -> dict:
        """获取维度趋势"""
        recent = self.metrics_history[-last_n:]
        if len(recent) < 2:
            return {"direction": "stable", "values": []}
        values = [m.dimension_scores.get(dimension, 0) for m in recent]
        diff = values[-1] - values[0]
        if diff > 0.1:
            direction = "improving"
        elif diff < -0.1:
            direction = "declining"
        else:
            direction = "stable"
        return {"direction": direction, "values": values}

    def get_metrics(self) -> dict:
        """获取当前所有维度"""
        return self.calculate_scores()

    def get_overall(self) -> float:
        """获取综合得分"""
        return self.get_overall_score()

    def get_report(self) -> str:
        """生成活人感报告"""
        scores = self.calculate_scores()
        overall = self.get_overall_score(scores)
        unique_emotions = len(set(self.current_session["emotions_expressed"]))

        lines = [f"活人感综合得分: {overall:.0%}"]
        for dim in self.DIMENSION_KEYS:
            score = scores.get(dim, 0)
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            lines.append(f"  {dim}: {bar} {score:.0%}")

        lines.append(f"  情绪种类: {unique_emotions} 种")
        lines.append(f"  身体引用: {self.current_session['physical_references']} 次")
        lines.append(f"  脆弱表达: {self.current_session['vulnerability_count']} 次")
        return "\n".join(lines)


# Alias for backward compatibility
LivenessMetrics = LivenessScore
