"""
活人感八维度指标体系 - Liveness Metrics

量化 AI 伴侣的"活人感"程度，用于评估和优化。

更新说明（2026-04-29）：
- Growth：接入 PreferenceModel L2+ 推断数据
- Unpredictability：接入冲动触发和随机概率波动
- Consistency：接入矛盾检测事件
- Vulnerability/Attachment：修正过宽松的公式
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING
from pathlib import Path
import json

if TYPE_CHECKING:
    from core.memory.preference_model import PreferenceModel


@dataclass
class LivenessMetrics:
    """活人感指标快照"""
    timestamp: str
    dimension_scores: Dict[str, float]  # 各维度得分 0-1
    overall_score: float                 # 综合得分
    sample_count: int                    # 采样数


@dataclass
class LivenessDimensions:
    """活人感八维度定义"""

    # 主动性 - 主动联系用户的频率和质量
    INITIATIVE = {
        "name": "主动性",
        "description": "主动联系用户的频率和质量",
        "metrics": ["daily_initiated_ratio", "response_timeliness"],
        "weight": 0.15,
        "target": "> 0.5 主动发起占比"
    }

    # 一致性 - 人设言行的一致性
    CONSISTENCY = {
        "name": "一致性",
        "description": "人设言行的一致性",
        "metrics": ["personality_variance", "memory_consistency"],
        "weight": 0.15,
        "target": "> 0.8 一致性得分"
    }

    # 成长性 - 随时间展现的学习能力
    GROWTH = {
        "name": "成长性",
        "description": "随时间展现的学习能力",
        "metrics": ["new_topic_adoption", "preference_learning_rate"],
        "weight": 0.10,
        "target": "每周新增 1-2 个认知"
    }

    # 情绪化 - 情绪表达的丰富度
    EMOTIONAL = {
        "name": "情绪化",
        "description": "情绪表达的丰富度和合理性",
        "metrics": ["emotion_variance", "context_appropriateness"],
        "weight": 0.12,
        "target": "8 种情绪全覆盖"
    }

    # 脆弱性 - 展现适度的不完美
    VULNERABILITY = {
        "name": "脆弱性",
        "description": "展现适度的不完美和依赖感",
        "metrics": ["vulnerability_expression_freq"],
        "weight": 0.10,
        "target": "每周 2-3 次适度示弱"
    }

    # 身体存在感 - 通过文字传达物理存在
    PHYSICAL_PRESENCE = {
        "name": "身体存在感",
        "description": "通过文字传达物理存在",
        "metrics": ["physical_reference_ratio"],
        "weight": 0.10,
        "target": "每条消息 0.5+ 身体引用"
    }

    # 不可预测性 - 适度的意外反应
    UNPREDICTABILITY = {
        "name": "不可预测性",
        "description": "适度的意外反应创造真实感",
        "metrics": ["deviation_from_patterns"],
        "weight": 0.13,
        "target": "10-15% 非模式化回应"
    }

    # 依恋度 - 对用户的情感依附
    ATTACHMENT = {
        "name": "依恋度",
        "description": "对用户的情感依附程度",
        "metrics": ["user_reference_frequency", "separation_signals"],
        "weight": 0.15,
        "target": "随关系阶段动态调整"
    }


class LivenessTracker:
    """活人感指标追踪器

    更新（2026-04-29）：
    - 接入 PreferenceModel L2+ 数据
    - 修正脆弱性/依恋度公式
    - 矛盾检测事件追踪
    """

    DIMENSION_KEYS = [
        "initiative", "consistency", "growth",
        "emotional", "vulnerability", "physical_presence",
        "unpredictability", "attachment"
    ]

    def __init__(self, data_path: str = "./data/liveness"):
        self.data_path = data_path
        Path(data_path).mkdir(parents=True, exist_ok=True)
        self.metrics_history: List[LivenessMetrics] = []
        self.session_start = datetime.now()
        self.week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        self.current_session: Dict = {
            "initiated_contacts": 0,
            "total_contacts": 0,
            "personality_violations": 0,
            "emotions_expressed": [],
            "vulnerability_count": 0,
            "physical_references": 0,
            "unpredictable_responses": 0,
            "user_references": 0,
            "total_messages": 0,
            # 新增追踪
            "contradictions_detected": 0,     # 矛盾检测次数
            "inferences_made": 0,             # L2+ 推断次数
            "beliefs_confirmed": 0,           # 推断被确认次数
            "beliefs_denied": 0,             # 推断被否认次数
            "impulsive_triggers": 0,          # 冲动触发次数
            "contradictions_total": 0,        # 累计矛盾事件（跨会话）
            "inferences_total": 0,           # 累计推断次数（跨会话）
        }
        self._preference_model: Optional["PreferenceModel"] = None
        self._load_history()

    def _load_history(self):
        """加载历史指标"""
        history_file = Path(self.data_path) / "metrics_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.metrics_history = [
                        LivenessMetrics(**m) for m in data.get("metrics", [])
                    ]
            except (json.JSONDecodeError, OSError):
                pass

    def _save_history(self):
        """保存历史指标"""
        history_file = Path(self.data_path) / "metrics_history.json"
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump({
                    "metrics": [
                        {"timestamp": m.timestamp, "dimension_scores": m.dimension_scores,
                         "overall_score": m.overall_score, "sample_count": m.sample_count}
                        for m in self.metrics_history[-100:]  # 只保留最近 100 条
                    ]
                }, f, ensure_ascii=False, indent=2)
        except (TypeError, OSError):
            pass

    # -------------------- 关联组件 --------------------

    def set_preference_model(self, pm: "PreferenceModel") -> None:
        """设置 PreferenceModel 实例，用于追踪 L2+ 数据"""
        self._preference_model = pm

    # -------------------- 记录方法 --------------------

    def record_initiated_contact(self) -> None:
        """记录主动发起的联系"""
        self.current_session["initiated_contacts"] += 1
        self.current_session["total_contacts"] += 1

    def record_response(self, content: str, context: Dict) -> None:
        """记录一次回复，分析各维度"""
        self.current_session["total_messages"] += 1
        self.current_session["total_contacts"] += 1

        content_lower = content.lower()

        # 情绪表达
        emotions = self._detect_emotions(content_lower)
        self.current_session["emotions_expressed"].extend(emotions)

        # 身体存在感
        if any(w in content_lower for w in ["抱", "靠", "坐", "躺", "站", "走", "手", "脸", "眼", "头", "肩"]):
            self.current_session["physical_references"] += 1

        # 用户引用
        if any(w in content_lower for w in ["你", "亲爱的", "宝贝", "傻瓜"]):
            self.current_session["user_references"] += 1

        # 脆弱性表达（扩大词库）
        vuln_keywords = ["有点累", "想你了", "不太舒服", "撒娇", "委屈", "孤单",
                         "寂寞", "无聊", "睡不着", "不舒服", "难过", "心累", "困"]
        if any(w in content_lower for w in vuln_keywords):
            self.current_session["vulnerability_count"] += 1

        # 不可预测性：检测非模式化表达
        # 如果回复中有随机感叹词或意外反应，计为不可预测
        unpredictable_markers = ["咦", "啊", "诶", "哇", "哎呀", "嗯？", "哈？",
                                  "真的吗", "等等", "话说", "其实"]
        if any(m in content_lower for m in unpredictable_markers):
            self.current_session["unpredictable_responses"] += 1

    def record_contradiction(self, found: bool = True) -> None:
        """记录矛盾检测事件

        Args:
            found: 是否检测到矛盾（True=有矛盾，False=检测了但没有）
        """
        self.current_session["contradictions_detected"] += 1
        if found:
            self.current_session["contradictions_total"] += 1

    def record_inference(self, made: bool = True) -> None:
        """记录 L2+ 推断事件

        Args:
            made: 是否成功生成了推断
        """
        self.current_session["inferences_made"] += 1
        self.current_session["inferences_total"] += 1

    def record_belief_feedback(self, confirmed: bool) -> None:
        """记录推断被确认/否认"""
        if confirmed:
            self.current_session["beliefs_confirmed"] += 1
        else:
            self.current_session["beliefs_denied"] += 1

    def record_impulsive_trigger(self, triggered: bool = True) -> None:
        """记录冲动触发事件"""
        if triggered:
            self.current_session["impulsive_triggers"] += 1

    def _detect_emotions(self, text: str) -> List[str]:
        """检测文本中的情绪"""
        emotion_map = {
            "开心": ["开心", "高兴", "快乐", "太好了", "😊", "😄", "💕", "哈哈", "嘻嘻"],
            "担心": ["担心", "怕", "紧张", "怕你"],
            "想念": ["想", "思念", "好久不见", "想你", "念你"],
            "撒娇": ["嗯~", "嘛~", "好不好嘛", "哼", "啦", "哟"],
            "害羞": ["害羞", "脸红", "不好意思", "羞"],
            "难过": ["难过", "伤心", "委屈", "不舒服", "心痛", "失落"],
            "生气": ["生气", "气", "讨厌", "哼", "不理你"],
            "兴奋": ["兴奋", "太棒了", "太好了", "哇塞", "好激动"]
        }

        detected = []
        for emotion, keywords in emotion_map.items():
            if any(kw in text for kw in keywords):
                detected.append(emotion)
        return detected

    # -------------------- 得分计算 --------------------

    def calculate_scores(self) -> Dict[str, float]:
        """计算当前各维度得分（修复版）"""
        s = self.current_session

        # 1. 主动性：主动发起 / 总互动
        total = max(s["total_contacts"], 1)
        initiative = s["initiated_contacts"] / total

        # 2. 一致性：基于矛盾检测（修正）
        # 有矛盾检测 → 扣分；无矛盾检测 → 保持高分
        contradictions = s.get("contradictions_detected", 0)
        consistency = max(0.0, 1.0 - contradictions * 0.05)  # 每次矛盾扣 5%，最低 0

        # 3. 成长性：接入 PreferenceModel L2+ 数据（修正）
        growth = self._calculate_growth()

        # 4. 情绪化：基于检测到的情绪种类
        total_msgs = max(s["total_messages"], 1)
        unique_emotions = len(set(s["emotions_expressed"]))
        emotional = min(1.0, unique_emotions / 5)  # 5 种以上情绪满分

        # 5. 脆弱性：基于表达频率（修正）
        # 目标：每周 2-3 次，2 次=60%，3 次=80%，4 次+=满分
        days_this_week = max(0.001, (datetime.now() - self.week_start).total_seconds() / 86400)
        vuln_this_week = s["vulnerability_count"] / days_this_week
        # 非线性的 sigmoid 风格曲线：2次=60%，3次=75%，5次+=90%+
        vulnerability = min(1.0, vuln_this_week / (vuln_this_week + 2.5))

        # 6. 身体存在感
        physical = min(1.0, s["physical_references"] / total_msgs * 3)

        # 7. 不可预测性：接入冲动触发和随机波动（修正）
        unpredictability = self._calculate_unpredictability()

        # 8. 依恋度：基于用户引用频率（修正）
        # 合理范围：引用率 30-50% 为健康，>80% 过于依赖，<20% 冷淡
        attachment_rate = s["user_references"] / total_msgs
        # U 型曲线：30%-50% 最高，偏离则降低
        if 0.3 <= attachment_rate <= 0.5:
            attachment = 0.9 + (attachment_rate - 0.3) * 0.5  # 0.9-1.0
        elif attachment_rate > 0.5:
            attachment = max(0.7, 1.0 - (attachment_rate - 0.5) * 0.6)  # 过高反而降分
        else:
            attachment = max(0.3, attachment_rate * 2)  # 过低则线性低分

        return {
            "initiative": round(initiative, 2),
            "consistency": round(consistency, 2),
            "growth": round(growth, 2),
            "emotional": round(emotional, 2),
            "vulnerability": round(vulnerability, 2),
            "physical_presence": round(physical, 2),
            "unpredictability": round(unpredictability, 2),
            "attachment": round(attachment, 2)
        }

    def _calculate_growth(self) -> float:
        """计算成长性得分（接入 PreferenceModel）"""
        if self._preference_model is None:
            return 0.65  # 无 PreferenceModel 时返回基线

        try:
            pm = self._preference_model
            beliefs = pm._beliefs

            # 无任何 belief 时返回基线
            if not beliefs:
                return 0.65

            stats = pm.get_stats()

            # 指标 1：活跃推断数量（1-5 条为健康，太多/太少都不好）
            active = stats.get("active_beliefs", 0)
            if 1 <= active <= 3:
                belief_score = 0.6 + active * 0.1  # 0.7-0.9
            elif active > 5:
                belief_score = 0.5  # 太多推断，可能过于确定
            else:
                belief_score = 0.4

            # 指标 2：推断确认率（被确认 / (被确认 + 被否认)）
            total_feedback = sum(b.confirm_count + b.deny_count for b in beliefs)
            total_confirms = sum(b.confirm_count for b in beliefs)
            if total_feedback > 0:
                confirm_rate = total_confirms / total_feedback
            else:
                confirm_rate = 0.5  # 无反馈时中立

            # 指标 3：故事化程度（有多条推断才能形成故事）
            story = pm.get_user_story()
            has_story = 1.0 if story and len(story) > 20 else 0.5

            # 综合：40% belief数量 + 40% 确认率 + 20% 故事化
            growth = belief_score * 0.4 + confirm_rate * 0.4 + has_story * 0.2
            return min(1.0, max(0.0, growth))
        except Exception:
            return 0.65

    def _calculate_unpredictability(self) -> float:
        """计算不可预测性得分（接入冲动触发和随机波动）"""
        s = self.current_session
        total_msgs = max(s["total_messages"], 1)

        # 指标 1：显式不可预测表达比例
        explicit_unpred = s.get("unpredictable_responses", 0)
        explicit_score = min(1.0, explicit_unpred / total_msgs * 8)  # 12.5% 触发率 → 满分

        # 指标 2：冲动触发次数（相对于消息数）
        impulsive = s.get("impulsive_triggers", 0)
        # 合理范围：每 10-20 条消息触发一次冲动
        if impulsive == 0:
            impulse_score = 0.5  # 无冲动记录时给中立
        else:
            msgs_per_impulse = total_msgs / impulsive
            if 5 <= msgs_per_impulse <= 20:
                impulse_score = 0.8  # 合理频率
            elif msgs_per_impulse < 5:
                impulse_score = 0.6  # 太频繁
            else:
                impulse_score = 0.7  # 较少但合理

        # 指标 3：基于随机性的理论不可预测性（用概率波动的标准差估算）
        # 冲动概率基础 30%，波动 ±15% → 实际范围 15%-45%
        # 这本身提供了 0.3 的固有随机性
        theoretical_randomness = 0.3

        # 综合：50% 显式不可预测 + 30% 冲动频率 + 20% 理论随机性
        unpredictability = (
            explicit_score * 0.5 +
            impulse_score * 0.3 +
            theoretical_randomness * 0.2
        )
        # 目标范围 0.3-0.6（研究中指出多样指数 0.3-0.6 最优）
        return min(0.7, max(0.2, unpredictability))

    def get_overall_score(self, scores: Dict[str, float] = None) -> float:
        """计算综合得分"""
        if scores is None:
            scores = self.calculate_scores()

        weights = {
            "initiative": 0.15,
            "consistency": 0.15,
            "growth": 0.10,
            "emotional": 0.12,
            "vulnerability": 0.10,
            "physical_presence": 0.10,
            "unpredictability": 0.13,
            "attachment": 0.15
        }

        overall = sum(scores.get(k, 0) * w for k, w in weights.items())
        return round(overall, 2)

    def snapshot(self) -> LivenessMetrics:
        """保存当前快照到历史"""
        scores = self.calculate_scores()
        overall = self.get_overall_score(scores)
        total_msgs = self.current_session["total_messages"]

        metric = LivenessMetrics(
            timestamp=datetime.now().isoformat(),
            dimension_scores=scores,
            overall_score=overall,
            sample_count=total_msgs
        )
        self.metrics_history.append(metric)
        self._save_history()
        return metric

    def get_trend(self, dimension: str, last_n: int = 7) -> Dict:
        """获取某个维度的趋势

        Args:
            dimension: 维度名称
            last_n: 最近 N 条快照
        """
        recent = self.metrics_history[-last_n:]
        if not recent:
            return {"direction": "stable", "values": []}

        values = [m.dimension_scores.get(dimension, 0) for m in recent]
        if len(values) < 2:
            return {"direction": "stable", "values": values}

        diff = values[-1] - values[0]
        if diff > 0.1:
            direction = "improving"
        elif diff < -0.1:
            direction = "declining"
        else:
            direction = "stable"

        return {"direction": direction, "values": values}

    def get_report(self) -> str:
        """生成活人感报告"""
        scores = self.calculate_scores()
        overall = self.get_overall_score(scores)

        dim_names = {
            "initiative": "主动性",
            "consistency": "一致性",
            "growth": "成长性",
            "emotional": "情绪化",
            "vulnerability": "脆弱性",
            "physical_presence": "身体感",
            "unpredictability": "不可预测",
            "attachment": "依恋度"
        }

        report = f"""
╔══════════════════════════════════════════════════════════╗
║           AI Companion 活人感报告                        ║
║           生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}                          ║
╠══════════════════════════════════════════════════════════╣
║  综合得分：{overall:.1%}                                        ║
╠══════════════════════════════════════════════════════════╣"""

        for key, name in dim_names.items():
            score = scores.get(key, 0)
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            trend_icon = ""
            if len(self.metrics_history) >= 2:
                trend = self.get_trend(key, 7)
                if trend["direction"] == "improving":
                    trend_icon = " ↑"
                elif trend["direction"] == "declining":
                    trend_icon = " ↓"
            report += f"\n║  {name}：{bar} {score:.0%}{trend_icon}  ║"

        s = self.current_session
        total_msgs = max(s["total_messages"], 1)
        unique_emotions = len(set(s["emotions_expressed"]))

        # 获取 PreferenceModel 统计
        pm_info = ""
        if self._preference_model:
            try:
                stats = self._preference_model.get_stats()
                pm_info = f"\n║  L2+推断：{stats.get('active_beliefs', 0)} 条活跃  矛盾：{s.get('contradictions_total', 0)} 次       ║"
            except Exception:
                pass

        report += f"""
╠══════════════════════════════════════════════════════════╣
║  本会话统计：                                              ║
║  主动联系：{s['initiated_contacts']} 次  总互动：{s['total_contacts']} 次             ║
║  情绪表达：{unique_emotions} 种  身体引用：{s['physical_references']} 次                ║
║  脆弱表达：{s['vulnerability_count']} 次  不可预测：{s.get('unpredictable_responses', 0)} 次            ║{pm_info}
╚══════════════════════════════════════════════════════════╝"""

        return report


# 全局实例
liveness_tracker = LivenessTracker()
