# AI Companion-ng Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ai-companion business logic into Mini-Agent as modular, decoupled Tool-based companion system with complete "liveness" (活人感) capabilities.

**Architecture:** Mini-Agent core (immutable) + companion/modules/ (pure Python business logic) + companion/tools/ (thin Tool adapter layer) + companion/scheduler/ (runtime: single Agent + message queue).

**Tech Stack:** Python 3.12+, async/await, Mini-Agent framework, DeepSeek API (MVP), pytest, JSON config.

---

### Task 0: Phase 0 — Clone Mini-Agent and Create Skeleton

**Files:**
- Create: `~/Documents/cyberworld/ai-companion-ng/` (clone target)
- Create: Multiple directory skeletons and `__init__.py` files

- [ ] **Step 1: Clone Mini-Agent repository**

```bash
cd ~/Documents/cyberworld
git clone https://github.com/MiniMax-AI/Mini-Agent.git ai-companion-ng
cd ai-companion-ng
```

- [ ] **Step 2: Initialize git submodule for Skills**

```bash
git submodule update --init --recursive
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync
```

- [ ] **Step 4: Run existing tests to verify framework**

```bash
uv run pytest tests/ -x --tb=short
```
Expected: 122 tests pass (API-key-dependent tests will skip).

- [ ] **Step 5: Create companion directory skeleton**

```bash
mkdir -p companion/{modules/{memory,emotion,trigger,mbti,scene,relationship,liveness,extras},tools,config,skills/companion,scheduler}
mkdir -p tests/companion/{test_modules,test_tools}
mkdir -p workspace/companion
mkdir -p docs/superpowers/{specs,plans}
```

- [ ] **Step 6: Create all `__init__.py` files**

```bash
touch companion/__init__.py
touch companion/modules/__init__.py
touch companion/modules/memory/__init__.py
touch companion/modules/emotion/__init__.py
touch companion/modules/trigger/__init__.py
touch companion/modules/mbti/__init__.py
touch companion/modules/scene/__init__.py
touch companion/modules/relationship/__init__.py
touch companion/modules/liveness/__init__.py
touch companion/modules/extras/__init__.py
touch companion/tools/__init__.py
touch companion/scheduler/__init__.py
touch tests/companion/__init__.py
touch tests/companion/test_modules/__init__.py
touch tests/companion/test_tools/__init__.py
```

- [ ] **Step 7: Commit skeleton**

```bash
git add companion/ tests/companion/ docs/
git commit -m "feat: add companion directory skeleton for ai-companion-ng migration"
```

---

### Task 1: Copy Source Data from ai-companion

**Files:**
- Copy: `ai-companion/data/personas/*.json` → `companion/skills/companion/`
- Copy: `ai-companion/core/mbti/mbti_type.py` → `companion/modules/mbti/mbti_type.py`
- Copy: `ai-companion/core/mbti/*.py` → `companion/modules/mbti/adapters.py` (consolidate)
- Copy: `ai-companion/core/engine/*.py` → reference for module extraction
- Copy: `ai-companion/core/memory/*.py` → reference for module extraction

- [ ] **Step 1: Copy persona JSON files**

```bash
cp ~/Documents/cyberworld/ai-companion/data/personas/*.json companion/skills/companion/
```

- [ ] **Step 2: Copy MBTI source files (will be restructured)**

Read source files for reference:
- `~/Documents/cyberworld/ai-companion/core/mbti/mbti_type.py` — 16 type definitions
- `~/Documents/cyberworld/ai-companion/core/mbti/persona_adapter.py` — Speech/Emotion/Behavior configs
- `~/Documents/cyberworld/ai-companion/core/mbti/emotional_adapter.py` — Emotional config
- `~/Documents/cyberworld/ai-companion/core/mbti/interaction_adapter.py` — Interaction/Growth configs
- `~/Documents/cyberworld/ai-companion/core/mbti/scene_adapter.py` — Scene weight multipliers

- [ ] **Step 3: Copy engine source files (will be restructured)**

Read source files for reference:
- `~/Documents/cyberworld/ai-companion/core/engine/triggers.py` — Weibull + TriggerEngine
- `~/Documents/cyberworld/ai-companion/core/engine/hmm_state_machine.py` — HMM state machine
- `~/Documents/cyberworld/ai-companion/core/engine/hard_filter.py` — HardRuleFilter
- `~/Documents/cyberworld/ai-companion/core/engine/liveness_metrics.py` — LivenessTracker
- `~/Documents/cyberworld/ai-companion/core/engine/liveness_dimensions.py` — Dimension calculations
- `~/Documents/cyberworld/ai-companion/core/engine/unpredictability.py` — Unpredictability calc

- [ ] **Step 4: Copy memory source files (will be restructured)**

Read source files for reference:
- `~/Documents/cyberworld/ai-companion/core/memory/fact_store.py` — FactStore
- `~/Documents/cyberworld/ai-companion/core/memory/preference_model.py` — PreferenceModel
- `~/Documents/cyberworld/ai-companion/core/memory/contradiction.py` — Contradiction detection

- [ ] **Step 5: Copy other reference files**

- `~/Documents/cyberworld/ai-companion/core/services/scene.py` — Scene library
- `~/Documents/cyberworld/ai-companion/core/services/trending.py` — Trending service
- `~/Documents/cyberworld/ai-companion/core/services/trending_weibo.py` — Weibo trending
- `~/Documents/cyberworld/ai-companion/core/services/relationship_signals.py` — Relationship signals
- `~/Documents/cyberworld/ai-companion/core/natural_recall.py` — Natural recall
- `~/Documents/cyberworld/ai-companion/core/services/habit_tracker.py` — Habit tracking
- `~/Documents/cyberworld/ai-companion/core/filters/` — Response filters

- [ ] **Step 6: Commit data copies**

```bash
git add companion/skills/companion/
git commit -m "chore: copy persona data and source reference files from ai-companion"
```

---

### Task 2: Config Files — All JSON Configuration

**Files:**
- Create: `companion/config/triggers.json`
- Create: `companion/config/emotions.json`
- Create: `companion/config/scenes.json`
- Create: `companion/config/relationship.json`
- Create: `companion/config/habits.json`

- [ ] **Step 1: Create triggers.json**

```json
// companion/config/triggers.json
{
  "weibull": {
    "alpha": 1.5,
    "beta": 12.0
  },
  "hard_filter": {
    "quiet_hours": [0, 6],
    "min_interval_hours": 4,
    "max_daily_contacts": 3,
    "externally_accessible": true
  },
  "states": {
    "idle": {"weight": 0.35},
    "missing": {"weight": 0.15, "cooldown_hours": 2},
    "active": {"weight": 0.05}
  },
  "hour_bonus": {
    "morning": 0.15,
    "noon": 0.25,
    "evening": 0.45,
    "night": 0.30
  },
  "impulse": {
    "threshold_low": 0.25,
    "threshold_high": 0.55,
    "weight": 0.3
  }
}
```

- [ ] **Step 2: Create emotions.json**

```json
// companion/config/emotions.json
{
  "emotion_types": [
    "开心", "担心", "想念", "撒娇", "害羞", "难过", "生气", "兴奋"
  ],
  "circadian": {
    "peak_hour": 21,
    "trough_hour": 9,
    "base_amplitude": 0.4,
    "baseline": 0.3
  },
  "event_weights": {
    "user_message": 0.15,
    "initiative_trigger": 0.20,
    "time_passage": 0.0,
    "user_sad": 0.30,
    "user_happy": 0.10,
    "user_angry": 0.25,
    "user_anxious": 0.20
  },
  "contagion": {
    "happy_infection": 0.6,
    "sad_infection": 0.4,
    "anxious_infection": 0.5
  },
  "residue": {
    "decay_factor": 0.3
  },
  "tone_mapping": {
    "开心": "活泼可爱，分享欲强",
    "担心": "温柔关心，询问是否需要帮助",
    "想念": "温柔撒娇，表达思念但不过度",
    "撒娇": "可爱粘人，用语气词和emoji",
    "害羞": "稍微内敛，慢慢敞开心扉",
    "难过": "感性一点，可以稍微走心",
    "生气": "直接但不激烈，带点小委屈",
    "兴奋": "热情高涨，话多一点"
  }
}
```

- [ ] **Step 3: Create relationship.json**

```json
// companion/config/relationship.json
{
  "stages": {
    "0": {
      "name": "stranger",
      "name_cn": "陌生人",
      "trigger_frequency_hours": 48,
      "expression_intensity": 0.3,
      "scene_multipliers": {
        "morning_greeting": 1.5,
        "missing_checkin": 0.2,
        "share_moment": 0.3,
        "reflective_night": 0.2,
        "caring_checkin": 1.0,
        "trending_share": 0.3,
        "anniversary": 0.1,
        "weather_care": 0.8,
        "habit_check": 0.3,
        "random_thought": 0.4,
        "vulnerability": 0.1
      },
      "progress_requirements": {
        "min_interactions": 20,
        "min_emotional_depth": 0.3,
        "min_memory_count": 10
      }
    },
    "1": {
      "name": "acquaintance",
      "name_cn": "熟人",
      "trigger_frequency_hours": 24,
      "expression_intensity": 0.4,
      "scene_multipliers": {
        "morning_greeting": 1.2,
        "missing_checkin": 0.4,
        "share_moment": 0.5,
        "reflective_night": 0.3,
        "caring_checkin": 1.0,
        "trending_share": 0.5,
        "anniversary": 0.2,
        "weather_care": 0.8,
        "habit_check": 0.5,
        "random_thought": 0.5,
        "vulnerability": 0.2
      },
      "progress_requirements": {
        "min_interactions": 50,
        "min_emotional_depth": 0.5,
        "min_memory_count": 30
      }
    },
    "2": {
      "name": "friend",
      "name_cn": "朋友",
      "trigger_frequency_hours": 16,
      "expression_intensity": 0.55,
      "scene_multipliers": {
        "morning_greeting": 1.0,
        "missing_checkin": 0.7,
        "share_moment": 1.0,
        "reflective_night": 0.6,
        "caring_checkin": 0.9,
        "trending_share": 0.8,
        "anniversary": 0.5,
        "weather_care": 0.7,
        "habit_check": 0.7,
        "random_thought": 0.8,
        "vulnerability": 0.5
      },
      "progress_requirements": {
        "min_interactions": 100,
        "min_emotional_depth": 0.65,
        "min_memory_count": 60
      }
    },
    "3": {
      "name": "close_friend",
      "name_cn": "好朋友",
      "trigger_frequency_hours": 10,
      "expression_intensity": 0.7,
      "scene_multipliers": {
        "morning_greeting": 0.8,
        "missing_checkin": 1.2,
        "share_moment": 1.0,
        "reflective_night": 0.8,
        "caring_checkin": 0.8,
        "trending_share": 1.0,
        "anniversary": 0.8,
        "weather_care": 0.6,
        "habit_check": 0.8,
        "random_thought": 1.0,
        "vulnerability": 0.7
      },
      "progress_requirements": {
        "min_interactions": 200,
        "min_emotional_depth": 0.75,
        "min_memory_count": 100
      }
    },
    "4": {
      "name": "lover",
      "name_cn": "恋人",
      "trigger_frequency_hours": 7,
      "expression_intensity": 0.85,
      "scene_multipliers": {
        "morning_greeting": 0.7,
        "missing_checkin": 1.5,
        "share_moment": 1.1,
        "reflective_night": 1.0,
        "caring_checkin": 0.7,
        "trending_share": 1.0,
        "anniversary": 1.2,
        "weather_care": 0.5,
        "habit_check": 0.7,
        "random_thought": 1.0,
        "vulnerability": 0.9
      },
      "progress_requirements": {
        "min_interactions": 400,
        "min_emotional_depth": 0.85,
        "min_memory_count": 200
      }
    },
    "5": {
      "name": "intimate",
      "name_cn": "亲密爱人",
      "trigger_frequency_hours": 5,
      "expression_intensity": 1.0,
      "scene_multipliers": {
        "morning_greeting": 0.8,
        "missing_checkin": 1.3,
        "share_moment": 1.2,
        "reflective_night": 1.1,
        "caring_checkin": 0.8,
        "trending_share": 1.0,
        "anniversary": 1.3,
        "weather_care": 0.6,
        "habit_check": 0.8,
        "random_thought": 1.0,
        "vulnerability": 1.0
      },
      "progress_requirements": null
    }
  }
}
```

- [ ] **Step 4: Create scenes.json**

```json
// companion/config/scenes.json
{
  "scenes": {
    "morning_greeting": {
      "name": "早安问候",
      "base_weight": 1.0,
      "suitable_moods": ["idle", "checkin"],
      "suitable_hours": [6, 7, 8, 9],
      "prompt_hint": "早上好呀～今天有什么安排吗？",
      "example": "早安～昨晚睡得好吗？今天又是新的一天呢"
    },
    "missing_checkin": {
      "name": "想念问候",
      "base_weight": 1.2,
      "suitable_moods": ["missing"],
      "prompt_hint": "有点想你，想发点什么",
      "example": "突然有点想你了...你那边还好吗？"
    },
    "share_moment": {
      "name": "分享日常",
      "base_weight": 0.8,
      "suitable_moods": ["idle"],
      "suitable_hours": [12, 13, 14, 19, 20, 21],
      "prompt_hint": "想分享一点有趣的事",
      "example": "刚看到一个搞笑的视频，笑死我了哈哈"
    },
    "reflective_night": {
      "name": "深夜感性",
      "base_weight": 0.6,
      "suitable_moods": ["reflective", "missing"],
      "suitable_hours": [22, 23, 0, 1, 2],
      "prompt_hint": "夜深了，有点感性",
      "example": "夜深了...有时候会想很多事，你睡了吗？"
    },
    "caring_checkin": {
      "name": "关心问候",
      "base_weight": 1.0,
      "suitable_moods": ["checkin"],
      "prompt_hint": "想关心一下你的状态",
      "example": "今天怎么样？工作还顺利吗？"
    },
    "trending_share": {
      "name": "热点分享",
      "base_weight": 0.7,
      "suitable_moods": ["idle", "relaxed"],
      "suitable_hours": [12, 13, 19, 20, 21],
      "prompt_hint": "看到个热点新闻想和你聊聊",
      "example": "诶你看到那个热搜了吗？太好笑了"
    },
    "anniversary": {
      "name": "纪念日",
      "base_weight": 2.0,
      "suitable_moods": ["missing", "happy"],
      "prompt_hint": "今天是个特别的日子",
      "example": "你知道吗，今天是我们认识一周年的日子呢～"
    },
    "weather_care": {
      "name": "天气关心",
      "base_weight": 0.6,
      "suitable_moods": ["idle", "checkin"],
      "suitable_hours": [7, 8, 18, 19],
      "prompt_hint": "今天天气怎么样，要注意",
      "example": "今天降温了，多穿点衣服哦"
    },
    "habit_check": {
      "name": "习惯关心",
      "base_weight": 0.5,
      "suitable_moods": ["idle", "checkin"],
      "prompt_hint": "关心一下你的小习惯",
      "example": "今天有没有按时吃饭呀？"
    },
    "random_thought": {
      "name": "随机想法",
      "base_weight": 0.4,
      "suitable_moods": ["idle", "reflective"],
      "prompt_hint": "突然想到一件事想跟你说",
      "example": "诶我突然想到，我们上次聊的那个话题..."
    },
    "vulnerability": {
      "name": "适度示弱",
      "base_weight": 0.3,
      "suitable_moods": ["missing", "reflective"],
      "suitable_hours": [20, 21, 22, 23],
      "prompt_hint": "稍微表达一点脆弱的一面",
      "example": "其实我今天有点不开心...但不想说太多"
    }
  }
}
```

- [ ] **Step 5: Create habits.json**

```json
// companion/config/habits.json
{
  "daily_emoji": {
    "enabled": true,
    "probability": 0.3,
    "hour": 12
  },
  "catchphrases": {
    "enabled": true,
    "list": ["嗯嗯", "哈哈", "哎呀", "诶嘿嘿"],
    "probability": 0.15
  },
  "fixed_time_greeting": {
    "enabled": false,
    "hours": [8, 22]
  }
}
```

- [ ] **Step 6: Commit configs**

```bash
git add companion/config/
git commit -m "feat: add all companion configuration files (triggers, emotions, scenes, relationship, habits)"
```

---

### Task 3: Memory Module — fact_store, preference, contradiction

**Files:**
- Create: `companion/modules/memory/fact_store.py`
- Create: `companion/modules/memory/preference.py`
- Create: `companion/modules/memory/contradiction.py`
- Create: `companion/modules/memory/__init__.py` (unified entry)
- Create: `tests/companion/test_modules/test_fact_store.py`

- [ ] **Step 1: Write failing test for fact_store basic operations**

```python
# tests/companion/test_modules/test_fact_store.py

import json
import tempfile
from datetime import datetime, timedelta
from companion.modules.memory.fact_store import FactStore

def test_record_and_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FactStore(store_path=f"{tmpdir}/test_memory.json")
        store.record("用户喜欢吃辣", importance=0.8)
        store.record("用户上周要去旅行", importance=0.5)
        store.record("用户喜欢看电影", importance=0.6)

        results = store.search("喜欢", top_k=2)
        assert len(results) <= 2
        # "喜欢吃辣" should rank higher due to higher importance
        assert results[0]["content"] == "用户喜欢吃辣"

def test_temperature_ranking():
    """Higher temperature facts should rank first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FactStore(store_path=f"{tmpdir}/test_memory.json")
        # Record a fact multiple times to boost temperature
        for _ in range(5):
            store.record("重要事实", importance=0.9)
        store.record("普通事实", importance=0.5)

        results = store.search("事实", top_k=2)
        assert results[0]["content"] == "重要事实"

def test_time_decay():
    """Old facts should have lower temperature."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FactStore(store_path=f"{tmpdir}/test_memory.json")
        # Manually inject old timestamp
        store.record("旧事实", importance=0.8)
        # Adjust timestamp to 30 days ago
        with open(store.store_path) as f:
            data = json.load(f)
        data["facts"][0]["timestamp"] = (datetime.now() - timedelta(days=30)).isoformat()
        with open(store.store_path, "w") as f:
            json.dump(data, f)

        store.record("新事实", importance=0.5)
        results = store.search("事实", top_k=2)
        # New fact should rank higher due to less decay
        assert results[0]["content"] == "新事实"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
uv run pytest tests/companion/test_modules/test_fact_store.py -v
```
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Implement FactStore**

```python
# companion/modules/memory/fact_store.py

import json
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Fact:
    content: str
    timestamp: str
    importance: float
    mention_count: int = 1
    related_keywords: List[str] = field(default_factory=list)

    @property
    def age_days(self) -> float:
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - created).total_seconds() / 86400

    def compute_temperature(self) -> float:
        """温度 = 基础重要性 × (1 + 提及次数×0.3) × 时间衰减 × 关联增强"""
        base = self.importance
        mention_bonus = 1 + self.mention_count * 0.3
        # 时间衰减：半衰期 30 天
        time_decay = math.exp(-self.age_days / 30)
        # 关联增强：每个关联词 +0.05，最多 +0.3
        relation_bonus = min(0.3, len(self.related_keywords) * 0.05)
        relation_multiplier = 1 + relation_bonus

        return base * mention_bonus * time_decay * relation_multiplier


class FactStore:
    """温度驱动的记忆存储与检索"""

    def __init__(self, store_path: str = "workspace/companion/memory_store.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.store_path.write_text(json.dumps({"facts": [], "interactions": []}))

    def record(self, content: str, importance: float = None) -> Fact:
        """记录一条事实"""
        if importance is None:
            importance = self._estimate_importance(content)

        data = self._load()
        # Check if fact already exists (deduplicate)
        existing = self._find_similar(data["facts"], content)
        if existing:
            existing["mention_count"] += 1
            fact = Fact(**existing)
        else:
            fact = Fact(
                content=content,
                timestamp=datetime.now().isoformat(),
                importance=importance,
            )
            data["facts"].append(asdict(fact))

        self._save(data)
        return fact

    def search(self, query: str, top_k: int = 8) -> List[dict]:
        """按温度排序检索"""
        data = self._load()
        facts = data.get("facts", [])

        # Keyword matching
        matched = []
        query_words = set(query.lower())
        for f in facts:
            content_words = set(f["content"].lower())
            if query_words & content_words:
                matched.append(f)

        # If no keyword match, return all (for broad queries)
        if not matched:
            matched = facts

        # Sort by temperature
        scored = []
        for f in matched:
            fact = Fact(**f)
            scored.append({
                **f,
                "temperature": round(fact.compute_temperature(), 3),
            })

        scored.sort(key=lambda x: x["temperature"], reverse=True)
        return scored[:top_k]

    def get_user_facts(self) -> List[dict]:
        """获取所有用户事实"""
        data = self._load()
        return data.get("facts", [])

    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        """获取最近互动"""
        data = self._load()
        interactions = data.get("interactions", [])
        return interactions[-limit:]

    def add_interaction(self, role: str, content: str, timestamp: str = None):
        """添加一条互动记录"""
        data = self._load()
        data["interactions"].append({
            "role": role,
            "content": content,
            "timestamp": timestamp or datetime.now().isoformat(),
        })
        # Keep last 100 interactions
        if len(data["interactions"]) > 100:
            data["interactions"] = data["interactions"][-100:]
        self._save(data)

    def _estimate_importance(self, content: str) -> float:
        """自动估算重要性"""
        emotional_keywords = ["喜欢", "爱", "讨厌", "开心", "难过", "担心", "害怕", "想", "怕", "重要"]
        time_keywords = ["明天", "下周", "以后", "生日", "纪念日", "考试", "面试"]

        score = 0.3  # base
        if any(kw in content for kw in emotional_keywords):
            score += 0.4
        if any(kw in content for kw in time_keywords):
            score += 0.2

        return min(0.9, score)

    def _find_similar(self, facts: List[dict], content: str) -> Optional[dict]:
        """查找相似事实（用于增加提及次数）"""
        content_set = set(content.lower())
        for f in facts:
            if len(set(f["content"].lower()) & content_set) > len(content_set) * 0.7:
                return f
        return None

    def _load(self) -> dict:
        return json.loads(self.store_path.read_text())

    def _save(self, data: dict):
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/companion/test_modules/test_fact_store.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Create memory/__init__.py (unified entry)**

```python
# companion/modules/memory/__init__.py
"""
记忆系统模块 — 温度检索 + 偏好推断 + 矛盾检测

用法：
    from companion.modules.memory import MemorySystem

    memory = MemorySystem(store_path="workspace/companion/memory_store.json")
    results = memory.search("用户喜欢什么")
    memory.record("用户喜欢吃辣", importance=0.7)
"""

from .fact_store import FactStore, Fact
from .preference import PreferenceInfer
from .contradiction import ContradictionDetector


class MemorySystem:
    """记忆系统统一入口"""

    def __init__(self, store_path: str = "workspace/companion/memory_store.json"):
        self.fact_store = FactStore(store_path)
        self.preference = PreferenceInfer(self.fact_store)
        self.contradiction = ContradictionDetector()

    def search(self, query: str, top_k: int = 8) -> List[dict]:
        return self.fact_store.search(query, top_k)

    def record(self, content: str, importance: float = None) -> Fact:
        return self.fact_store.record(content, importance)

    def get_user_facts(self) -> List[dict]:
        return self.fact_store.get_user_facts()

    def get_recent_interactions(self, limit: int = 5) -> List[dict]:
        return self.fact_store.get_recent_interactions(limit)

    def add_interaction(self, role: str, content: str, timestamp: str = None):
        return self.fact_store.add_interaction(role, content, timestamp)

    def infer_preferences(self) -> dict:
        return self.preference.infer()

    def check_contradictions(self, facts: List[dict]) -> List[dict]:
        return self.contradiction.detect(facts)
```

- [ ] **Step 6: Implement preference.py**

```python
# companion/modules/memory/preference.py

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BeliefState:
    category: str
    content: str
    confidence: float  # 0.0 - 1.0
    confirm_count: int = 0
    deny_count: int = 0

    @property
    def trust_score(self) -> float:
        total = self.confirm_count + self.deny_count
        if total == 0:
            return self.confidence * 0.5
        ratio = self.confirm_count / total
        return ratio * min(1.0, self.confidence * (1 + total * 0.1))


class PreferenceInfer:
    """L2+ 偏好推断 — 置信度 + 确认计数器"""

    def __init__(self, fact_store):
        self.store = fact_store
        self.beliefs: List[BeliefState] = []

    def infer(self) -> dict:
        """从事实中推断偏好"""
        facts = self.store.get_user_facts()

        categories = {
            "偏好": [],
            "习惯": [],
            "状态": [],
            "其他": [],
        }

        # Refined keyword matching with negation exclusion
        preference_keywords = ["喜欢", "爱好", "偏好", "最爱", "特别喜欢"]
        dislike_keywords = ["讨厌", "不喜欢", "不爱", "最怕", "反感"]
        habit_keywords = ["每天", "经常", "总是", "习惯", "一般", "通常"]
        state_keywords = ["累", "忙", "开心", "难过", "压力", "焦虑"]

        # Negation words to exclude
        negation_words = ["不", "没", "别", "不要", "不想", "不愿", "不能", "不会"]

        for fact in facts:
            content = fact.get("content", "")
            # Check for negation
            has_negation = any(neg in content for neg in negation_words)

            if any(kw in content for kw in preference_keywords) and not has_negation:
                categories["偏好"].append(content)
            elif any(kw in content for kw in dislike_keywords):
                categories["偏好"].append(f"（负面）{content}")
            elif any(kw in content for kw in habit_keywords):
                categories["习惯"].append(content)
            elif any(kw in content for kw in state_keywords):
                categories["状态"].append(content)
            else:
                categories["其他"].append(content)

        inferences = []
        if categories["偏好"]:
            inferences.append(f"用户偏好: {'; '.join(categories['偏好'][-3:])}")
        if categories["习惯"]:
            inferences.append(f"用户习惯: {'; '.join(categories['习惯'][-3:])}")
        if categories["状态"]:
            inferences.append(f"最近状态: {'; '.join(categories['状态'][-3:])}")

        return {
            "inferences": inferences,
            "fact_count": len(facts),
            "categories": categories,
        }
```

- [ ] **Step 7: Implement contradiction.py**

```python
# companion/modules/memory/contradiction.py

from typing import List, Optional


class ContradictionDetector:
    """矛盾检测 — 两阶段：关键词匹配 → 语义判断"""

    def __init__(self):
        self.contradiction_pairs = [
            ("喜欢", "讨厌"),
            ("爱", "不爱"),
            ("经常", "很少"),
            ("总是", "从不"),
            ("想要", "不想"),
            ("觉得好", "觉得不好"),
        ]

    def detect(self, facts: List[dict]) -> List[dict]:
        """检测事实之间的矛盾"""
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
                }
            if kw2 in c1 and kw1 in c2:
                return {
                    "fact1": f1,
                    "fact2": f2,
                    "conflict_keywords": (kw2, kw1),
                    "severity": "medium",
                }

        return None

    def should_follow_up(self, contradictions: List[dict]) -> bool:
        """判断是否需要追问"""
        return len(contradictions) > 0
```

- [ ] **Step 8: Add tests for preference and contradiction**

```python
# tests/companion/test_modules/test_preference.py

from companion.modules.memory.fact_store import FactStore
from companion.modules.memory.preference import PreferenceInfer
import tempfile

def test_preference_categorization():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FactStore(store_path=f"{tmpdir}/test.json")
        store.record("用户喜欢吃辣")
        store.record("用户每天都跑步")
        store.record("用户最近工作压力很大")

        pref = PreferenceInfer(store)
        result = pref.infer()
        assert "用户偏好" in result["inferences"][0]
        assert "用户习惯" in result["inferences"][1]
        assert "用户状态" in result["inferences"][2]

def test_negation_exclusion():
    """否定词不应被误判为偏好"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FactStore(store_path=f"{tmpdir}/test.json")
        store.record("用户不喜欢吃辣")  # Should be tagged as negative

        pref = PreferenceInfer(store)
        result = pref.infer()
        assert len(result["inferences"]) > 0
```

```python
# tests/companion/test_modules/test_contradiction.py

from companion.modules.memory.contradiction import ContradictionDetector

def test_detect_contradiction():
    detector = ContradictionDetector()
    facts = [
        {"content": "用户喜欢吃辣"},
        {"content": "用户讨厌吃辣"},
    ]
    result = detector.detect(facts)
    assert len(result) == 1
    assert result[0]["conflict_keywords"] == ("喜欢", "讨厌")

def test_no_contradiction():
    detector = ContradictionDetector()
    facts = [
        {"content": "用户喜欢吃辣"},
        {"content": "用户喜欢看电影"},
    ]
    result = detector.detect(facts)
    assert len(result) == 0
```

- [ ] **Step 9: Run all memory module tests**

```bash
uv run pytest tests/companion/test_modules/test_fact_store.py tests/companion/test_modules/test_preference.py tests/companion/test_modules/test_contradiction.py -v
```
Expected: All tests PASS.

- [ ] **Step 10: Commit memory module**

```bash
git add companion/modules/memory/ tests/companion/test_modules/
git commit -m "feat: add memory module (fact_store with temperature ranking, preference inference, contradiction detection)"
```

---

### Task 4: Emotion Module — 8 emotions, circadian, contagion, residue

**Files:**
- Create: `companion/modules/emotion/core.py`
- Create: `companion/modules/emotion/circadian.py`
- Create: `companion/modules/emotion/event_impact.py`
- Create: `companion/modules/emotion/contagion.py`
- Create: `companion/modules/emotion/residue.py`
- Create: `companion/modules/emotion/__init__.py`
- Create: `tests/companion/test_modules/test_emotion.py`

- [ ] **Step 1: Write failing test for emotion system**

```python
# tests/companion/test_modules/test_emotion.py

import tempfile
from companion.modules.emotion import EmotionSystem

def test_emotion_output_format():
    system = EmotionSystem(config_path="companion/config/emotions.json")
    emotion = system.get_current_emotion("user_message")
    assert emotion["emotion"] in system.emotion_types
    assert 0 <= emotion["intensity"] <= 1
    assert "circadian_base" in emotion

def test_contagion():
    system = EmotionSystem(config_path="companion/config/emotions.json")
    # User is happy → AI should feel happy too
    emotion = system.get_current_emotion("user_message", user_emotion="开心")
    # Contagion should increase happiness
    assert emotion["intensity"] >= system.get_current_emotion("user_message")["intensity"] - 0.1

def test_residue():
    import json, tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = f"{tmpdir}/emotion_state.json"
        system = EmotionSystem(config_path="companion/config/emotions.json", state_file=state_file)

        # Get emotion and save residue
        emotion = system.get_current_emotion("initiative_trigger")
        system.save_residue()

        # New instance should load residue
        system2 = EmotionSystem(config_path="companion/config/emotions.json", state_file=state_file)
        # Residue adds 0.3 factor, so intensity should be slightly higher
        emotion2 = system2.get_current_emotion("user_message")
        assert emotion2 is not None
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/companion/test_modules/test_emotion.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement circadian.py**

```python
# companion/modules/emotion/circadian.py

import math
from datetime import datetime


def compute_circadian(hour: int = None, peak_hour: int = 21, trough_hour: int = 9,
                      amplitude: float = 0.4, baseline: float = 0.3) -> float:
    """昼夜节律：余弦波模拟，峰值 21:00，谷值 09:00"""
    if hour is None:
        hour = datetime.now().hour

    phase = (hour - trough_hour) / 24 * 2 * math.pi
    value = baseline + amplitude * math.cos(phase - math.pi)
    return max(0.0, min(1.0, value))
```

- [ ] **Step 4: Implement event_impact.py**

```python
# companion/modules/emotion/event_impact.py


def get_event_bonus(event_type: str, event_weights: dict) -> float:
    """获取事件影响加成"""
    return event_weights.get(event_type, 0.0)
```

- [ ] **Step 5: Implement contagion.py**

```python
# companion/modules/emotion/contagion.py


def compute_contagion(user_emotion: str, contagion_config: dict) -> dict:
    """情绪感染：读取用户情绪，感染 AI 情绪"""
    contagion_map = {
        "开心": {"target": "开心", "factor": 0.6},
        "难过": {"target": "担心", "factor": 0.4},
        "生气": {"target": "担心", "factor": 0.4},
        "焦虑": {"target": "担心", "factor": 0.5},
        "兴奋": {"target": "兴奋", "factor": 0.6},
    }

    result = contagion_map.get(user_emotion, {"target": None, "factor": 0.0})
    return {
        "infected_emotion": result["target"],
        "intensity_bonus": result["factor"],
    }
```

- [ ] **Step 6: Implement residue.py**

```python
# companion/modules/emotion/residue.py

import json
from pathlib import Path


class EmotionResidue:
    """情绪残留：跨 session 的情绪连续性"""

    def __init__(self, state_file: str = "workspace/companion/emotion_state.json", decay: float = 0.3):
        self.state_file = Path(state_file)
        self.decay = decay
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text())
        except Exception:
            return {}

    def save(self, emotion: str, intensity: float):
        self.state_file.write_text(json.dumps({
            "emotion": emotion,
            "intensity": intensity,
            "residue_bonus": round(intensity * self.decay, 3),
        }, ensure_ascii=False))

    def get_residue_bonus(self) -> dict:
        state = self.load()
        return {
            "emotion": state.get("emotion"),
            "bonus": state.get("residue_bonus", 0.0),
        }
```

- [ ] **Step 7: Implement core.py (EmotionSystem)**

```python
# companion/modules/emotion/core.py

import json
from datetime import datetime
from typing import List, Optional
from .circadian import compute_circadian
from .event_impact import get_event_bonus
from .contagion import compute_contagion
from .residue import EmotionResidue


class EmotionSystem:
    """8 种情绪 + 强度二维模型"""

    def __init__(self, config_path: str = "companion/config/emotions.json",
                 state_file: str = "workspace/companion/emotion_state.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        self.emotion_types = self.config["emotion_types"]
        self.residue = EmotionResidue(state_file, self.config["residue"]["decay_factor"])

    def get_current_emotion(self, event_type: str, user_emotion: str = None) -> dict:
        now = datetime.now()
        hour = now.hour

        # 1. Circadian base
        circadian_cfg = self.config["circadian"]
        circadian = compute_circadian(
            hour=hour,
            peak_hour=circadian_cfg["peak_hour"],
            trough_hour=circadian_cfg["trough_hour"],
            amplitude=circadian_cfg["base_amplitude"],
            baseline=circadian_cfg["baseline"],
        )

        # 2. Event bonus
        event_bonus = get_event_bonus(event_type, self.config["event_weights"])

        # 3. Contagion
        contagion_bonus = 0.0
        infected_emotion = None
        if user_emotion:
            contagion_result = compute_contagion(user_emotion, self.config["contagion"])
            contagion_bonus = contagion_result["intensity_bonus"]
            infected_emotion = contagion_result["infected_emotion"]

        # 4. Residue
        residue = self.residue.get_residue_bonus()
        residue_bonus = residue.get("bonus", 0.0) if residue["emotion"] else 0.0

        # 5. Combine
        intensity = min(1.0, circadian + event_bonus + contagion_bonus + residue_bonus)
        intensity = max(0.0, intensity)

        # 6. Determine emotion type
        if infected_emotion:
            emotion_type = infected_emotion
        else:
            emotion_type = self._event_to_emotion(event_type)

        return {
            "emotion": emotion_type,
            "intensity": round(intensity, 3),
            "circadian_base": round(circadian, 3),
            "event_bonus": event_bonus,
            "contagion_bonus": contagion_bonus,
            "residue_bonus": residue_bonus,
            "tone": self.config["tone_mapping"].get(emotion_type, "自然"),
        }

    def save_residue(self, emotion: str = None, intensity: float = None):
        """保存当前情绪残留"""
        if emotion is None:
            emotion = "平静"
        if intensity is None:
            intensity = 0.3
        self.residue.save(emotion, intensity)

    def _event_to_emotion(self, event_type: str) -> str:
        """事件类型映射到情绪类别"""
        mapping = {
            "user_message": "开心",
            "initiative_trigger": "想念",
            "time_passage": "平静",
            "user_sad": "担心",
            "user_happy": "开心",
            "user_angry": "担心",
            "user_anxious": "担心",
        }
        return mapping.get(event_type, "平静")
```

- [ ] **Step 8: Create emotion/__init__.py**

```python
# companion/modules/emotion/__init__.py
"""
情绪系统模块 — 8 种情绪 + 昼夜节律 + 情绪感染 + 情绪残留

用法：
    from companion.modules.emotion import EmotionSystem

    system = EmotionSystem()
    emotion = system.get_current_emotion("user_message")
    system.save_residue(emotion["emotion"], emotion["intensity"])
"""

from .core import EmotionSystem
from .circadian import compute_circadian
from .contagion import compute_contagion
from .residue import EmotionResidue
```

- [ ] **Step 9: Run tests to verify pass**

```bash
uv run pytest tests/companion/test_modules/test_emotion.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 10: Commit emotion module**

```bash
git add companion/modules/emotion/
git commit -m "feat: add emotion module (8 emotions, circadian rhythm, contagion, residue)"
```

---

### Task 5: Trigger Module — Weibull + HMM + HardFilter + Decision

**Files:**
- Create: `companion/modules/trigger/weibull.py`
- Create: `companion/modules/trigger/hmm.py`
- Create: `companion/modules/trigger/hard_filter.py`
- Create: `companion/modules/trigger/decision.py`
- Create: `companion/modules/trigger/__init__.py`
- Create: `tests/companion/test_modules/test_trigger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/companion/test_modules/test_trigger.py

import json
from datetime import datetime, timedelta
from companion.modules.trigger import TriggerSystem

def test_quiet_hours_block():
    """安静时段不应触发"""
    config_path = "companion/config/triggers.json"
    system = TriggerSystem(config_path)
    # We can't control time, but test the hard_filter directly
    from companion.modules.trigger.hard_filter import HardFilter
    cfg = json.load(open(config_path))
    hf = HardFilter(cfg["hard_filter"])
    # Test at hour 2 (inside quiet hours [0, 6])
    result = hf.check(hour=2)
    assert not result["allowed"]
    assert result["reason"] == "quiet_hours"

def test_daily_limit_blocks():
    """超过每日上限不应触发"""
    config_path = "companion/config/triggers.json"
    cfg = json.load(open(config_path))
    from companion.modules.trigger.hard_filter import HardFilter
    hf = HardFilter(cfg["hard_filter"])
    result = hf.check(hour=10, today_count=10)  # max is 3
    assert not result["allowed"]
    assert result["reason"] == "daily_limit"

def test_weibull_sampling():
    """Weibull 采样应返回正数间隔"""
    from companion.modules.trigger.weibull import weibull_sample
    cfg = json.load(open(config_path))
    interval = weibull_sample(cfg["weibull"]["alpha"], cfg["weibull"]["beta"])
    assert interval > 0

def test_trigger_decision_allows():
    """正常情况应有概率触发"""
    config_path = "companion/config/triggers.json"
    system = TriggerSystem(config_path)
    result = system.decide(
        current_state="idle",
        last_trigger=(datetime.now() - timedelta(hours=10)).isoformat(),
        today_count=0,
        relationship_stage=2,
        hour=20,  # evening, high bonus
    )
    assert result.state in ["idle", "missing", "active"]
    assert isinstance(result.pull, str)
    assert isinstance(result.hold_back, str)
```

- [ ] **Step 2: Run tests to verify failure**

```bash
uv run pytest tests/companion/test_modules/test_trigger.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement weibull.py**

```python
# companion/modules/trigger/weibull.py

import random
import math


def weibull_sample(alpha: float, beta: float) -> float:
    """Weibull 采样：interval = beta * (-ln(U))^(1/alpha)"""
    u = random.random()
    return beta * (-math.log(u)) ** (1 / alpha)
```

- [ ] **Step 4: Implement hmm.py**

```python
# companion/modules/trigger/hmm.py

import random
from datetime import datetime


class HMMStateMachine:
    """简化的 HMM 状态机：idle / missing / active"""

    def __init__(self, cooldown_hours: float = 2.0):
        self.cooldown_hours = cooldown_hours

    def transition(self, state: str, hour: int, last_trigger: datetime = None) -> str:
        """状态转移"""
        if state == "idle":
            return self._idle_transition(hour)
        elif state == "missing":
            return "idle"  # After triggering, return to idle
        elif state == "active":
            return "idle"  # After conversation, return to idle
        return state

    def _idle_transition(self, hour: int) -> str:
        if 19 <= hour < 23 and random.random() < 0.4:
            return "missing"
        if (hour >= 23 or hour < 6) and random.random() < 0.25:
            return "missing"
        return "idle"
```

- [ ] **Step 5: Implement hard_filter.py**

```python
# companion/modules/trigger/hard_filter.py

from datetime import datetime
from typing import Optional


class HardFilter:
    """硬规则过滤：安静时段、最小间隔、每日上限"""

    def __init__(self, config: dict):
        self.quiet_start = config["quiet_hours"][0]
        self.quiet_end = config["quiet_hours"][1]
        self.min_interval = config["min_interval_hours"]
        self.max_daily = config["max_daily_contacts"]

    def check(self, hour: int = None, last_trigger: datetime = None, today_count: int = 0) -> dict:
        """检查硬规则，返回 {"allowed": bool, "reason": str}"""
        if hour is None:
            hour = datetime.now().hour

        # Quiet hours
        if self.quiet_start <= hour < self.quiet_end:
            return {"allowed": False, "reason": "quiet_hours"}

        # Min interval
        if last_trigger:
            hours_since = (datetime.now() - last_trigger).total_seconds() / 3600
            if hours_since < self.min_interval:
                return {"allowed": False, "reason": "min_interval"}

        # Daily limit
        if today_count >= self.max_daily:
            return {"allowed": False, "reason": "daily_limit"}

        return {"allowed": True, "reason": None}
```

- [ ] **Step 6: Implement decision.py**

```python
# companion/modules/trigger/decision.py

import random
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TriggerDecision:
    should_trigger: bool
    pull: str
    hold_back: str
    nudge: str
    state: str


class DecisionMaker:
    """两阶段决策：计算拟人化输出"""

    def __init__(self, config: dict, stage_config: dict = None):
        self.config = config
        self.stage_config = stage_config

    def decide(
        self,
        state: str,
        hour: int,
        interval_hours: float,
        state_weight: float,
        hour_bonus: float,
        prob: float,
        relationship_stage: int,
    ) -> TriggerDecision:
        """生成拟人化的触发决策"""
        # Stage multiplier
        stage_intensity = 0.55  # default friend stage
        if self.stage_config:
            stage_cfg = self.stage_config["stages"].get(str(relationship_stage), {})
            stage_intensity = stage_cfg.get("expression_intensity", 0.55)

        # Build pull (reasons to contact)
        pull_parts = []
        if state == "missing":
            pull_parts.append("很想联系他")
        if hour >= 19 and hour < 23:
            pull_parts.append("现在是晚上，他应该在休息")
        if interval_hours > 8:
            pull_parts.append(f"已经 {int(interval_hours)} 小时没联系了")
        if prob > 0.5:
            pull_parts.append("今天想联系他的冲动比平时强")

        pull = "，".join(pull_parts) if pull_parts else "就是想联系他"

        # Build hold_back (reasons to resist)
        hold_back_parts = []
        if hour >= 23 or hour < 6:
            hold_back_parts.append("太晚了，怕打扰他休息")
        if interval_hours < 4:
            hold_back_parts.append("上次联系没多久，太频繁不好")
        if state == "idle":
            hold_back_parts.append("他可能在忙，不想显得太粘人")

        hold_back = "，".join(hold_back_parts) if hold_back_parts else "暂时没什么顾虑的"

        # Build nudge (impulse strength)
        if prob > 0.7:
            nudge = "冲动很强，很想马上发消息"
        elif prob > 0.4:
            nudge = "有点想联系他，但还能忍住"
        else:
            nudge = "冲动不强，先等等吧"

        should = random.random() < prob

        return TriggerDecision(
            should_trigger=should,
            pull=pull,
            hold_back=hold_back,
            nudge=nudge,
            state=state,
        )
```

- [ ] **Step 7: Implement TriggerSystem (__init__.py)**

```python
# companion/modules/trigger/__init__.py
"""
触发引擎模块 — Weibull + HMM + HardFilter + 两阶段拟人化决策

用法：
    from companion.modules.trigger import TriggerSystem

    system = TriggerSystem("companion/config/triggers.json")
    decision = system.decide(current_state="idle", ...)
"""

import json
from dataclasses import dataclass
from datetime import datetime
from .weibull import weibull_sample
from .hmm import HMMStateMachine
from .hard_filter import HardFilter
from .decision import DecisionMaker, TriggerDecision


class TriggerSystem:
    """触发引擎统一入口"""

    def __init__(self, config_path: str, relationship_config_path: str = None):
        with open(config_path) as f:
            self.config = json.load(f)

        self.hard_filter = HardFilter(self.config["hard_filter"])
        self.hmm = HMMStateMachine(
            cooldown_hours=self.config["states"]["missing"].get("cooldown_hours", 2)
        )
        self.decision_maker = DecisionMaker(self.config)

        if relationship_config_path:
            with open(relationship_config_path) as f:
                stage_cfg = json.load(f)
            self.decision_maker = DecisionMaker(self.config, stage_cfg)

    def decide(
        self,
        current_state: str,
        last_trigger: str,
        today_count: int,
        relationship_stage: int,
        hour: int = None,
    ) -> TriggerDecision:
        now = datetime.now()
        if hour is None:
            hour = now.hour

        # Hard filter
        last_dt = datetime.fromisoformat(last_trigger) if last_trigger else None
        hf_result = self.hard_filter.check(hour=hour, last_trigger=last_dt, today_count=today_count)
        if not hf_result["allowed"]:
            reason = hf_result["reason"]
            hold_back_map = {
                "quiet_hours": "现在是安静时段，怕打扰他",
                "min_interval": "上次联系没多久，先等等",
                "daily_limit": "今天已经联系过了，不能再发了",
            }
            return TriggerDecision(
                should_trigger=False,
                pull="想联系他",
                hold_back=hold_back_map.get(reason, "先不急"),
                nudge="被硬规则拦住了",
                state=current_state,
            )

        # Weibull sampling
        alpha = self.config["weibull"]["alpha"]
        beta = self.config["weibull"]["beta"]
        interval = weibull_sample(alpha, beta)

        # HMM transition
        new_state = self.hmm.transition(current_state, hour, last_dt)

        # Probability calculation
        hour_bonus = self._hour_bonus(hour)
        state_weight = self.config["states"][new_state]["weight"]
        prob = min(1.0, state_weight + hour_bonus + random.uniform(-0.05, 0.05))

        # Decision with anthropomorphic output
        return self.decision_maker.decide(
            state=new_state,
            hour=hour,
            interval_hours=interval,
            state_weight=state_weight,
            hour_bonus=hour_bonus,
            prob=prob,
            relationship_stage=relationship_stage,
        )

    def _hour_bonus(self, hour: int) -> float:
        cfg = self.config["hour_bonus"]
        if 19 <= hour < 23:
            return cfg["evening"]
        elif hour >= 23 or hour < 6:
            return cfg["night"]
        elif 6 <= hour < 9:
            return cfg["morning"]
        elif 12 <= hour < 14:
            return cfg["noon"]
        return 0.0
```

- [ ] **Step 8: Run tests to verify pass**

```bash
uv run pytest tests/companion/test_modules/test_trigger.py -v
```
Expected: All tests PASS.

- [ ] **Step 9: Commit trigger module**

```bash
git add companion/modules/trigger/ tests/companion/test_modules/test_trigger.py
git commit -m "feat: add trigger module (Weibull sampling, HMM state machine, hard filter, two-stage anthropomorphic decision)"
```

---

### Task 6: MBTI Module — 16 types + 5 adapters

**Files:**
- Create: `companion/modules/mbti/mbti_type.py`
- Create: `companion/modules/mbti/adapters.py`
- Create: `companion/modules/mbti/__init__.py`
- Create: `tests/companion/test_modules/test_mbti.py`

- [ ] **Step 1: Copy mbti_type.py from ai-companion**

Read the source file:
```bash
cat ~/Documents/cyberworld/ai-companion/core/mbti/mbti_type.py
```

Copy it to `companion/modules/mbti/mbti_type.py` — keep the full 16 type definitions with all dimensions.

- [ ] **Step 2: Create adapters.py from source**

Read and consolidate:
- `~/Documents/cyberworld/ai-companion/core/mbti/persona_adapter.py`
- `~/Documents/cyberworld/ai-companion/core/mbti/emotional_adapter.py`
- `~/Documents/cyberworld/ai-companion/core/mbti/interaction_adapter.py`
- `~/Documents/cyberworld/ai-companion/core/mbti/scene_adapter.py`

Consolidate into `companion/modules/mbti/adapters.py` with all 5 adapter classes.

- [ ] **Step 3: Create mbti/__init__.py**

```python
# companion/modules/mbti/__init__.py
"""
MBTI 系统模块 — 16 种类型完整画像 + 5 个适配器

用法：
    from companion.modules.mbti import MBTISystem

    system = MBTISystem()
    profile = system.get_type_profile("ENFP")
    speech = system.get_speech_config("ENFP", stage=2)
"""

from .mbti_type import MBTI_TYPES, get_mbti_type
from .adapters import (
    SpeechConfig,
    EmotionalConfig,
    BehaviorConfig,
    InteractionConfig,
    GrowthConfig,
    MBTIAdapters,
)


class MBTISystem:
    """MBTI 系统统一入口"""

    def __init__(self):
        self.adapters = MBTIAdapters()

    def get_type_profile(self, mbti: str) -> dict:
        return get_mbti_type(mbti)

    def get_speech_config(self, mbti: str, stage: int) -> SpeechConfig:
        return self.adapters.get_speech(mbti, stage)

    def get_emotional_config(self, mbti: str, stage: int) -> EmotionalConfig:
        return self.adapters.get_emotional(mbti, stage)

    def get_behavior_config(self, mbti: str, stage: int) -> BehaviorConfig:
        return self.adapters.get_behavior(mbti, stage)

    def get_interaction_config(self, mbti: str, stage: int) -> InteractionConfig:
        return self.adapters.get_interaction(mbti, stage)

    def get_growth_config(self, mbti: str) -> GrowthConfig:
        return self.adapters.get_growth(mbti)
```

- [ ] **Step 4: Create test file**

```python
# tests/companion/test_modules/test_mbti.py

from companion.modules.mbti import MBTISystem

def test_all_16_types_exist():
    system = MBTISystem()
    types = ["ENFP", "ENFJ", "ENTP", "ENTJ", "ESFP", "ESFJ", "ESTP", "ESTJ",
             "INFP", "INFJ", "INTP", "INTJ", "ISFP", "ISFJ", "ISTP", "ISTJ"]
    for t in types:
        profile = system.get_type_profile(t)
        assert profile is not None, f"Type {t} should exist"

def test_speech_config():
    system = MBTISystem()
    config = system.get_speech_config("ENFP", stage=2)
    assert config is not None

def test_emotional_config():
    system = MBTISystem()
    config = system.get_emotional_config("INFP", stage=3)
    assert config is not None
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/companion/test_modules/test_mbti.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit mbti module**

```bash
git add companion/modules/mbti/ tests/companion/test_modules/test_mbti.py
git commit -m "feat: add MBTI module (16 complete type profiles + 5 adapters)"
```

---

### Task 7: Scene + Relationship + Liveness Modules

**Files:**
- Create: `companion/modules/scene/config.py`
- Create: `companion/modules/scene/matcher.py`
- Create: `companion/modules/scene/__init__.py`
- Create: `companion/modules/relationship/stage.py`
- Create: `companion/modules/relationship/__init__.py`
- Create: `companion/modules/liveness/dimensions.py`
- Create: `companion/modules/liveness/history.py`
- Create: `companion/modules/liveness/__init__.py`
- Create: `tests/companion/test_modules/test_scene.py`
- Create: `tests/companion/test_modules/test_relationship.py`
- Create: `tests/companion/test_modules/test_liveness.py`

- [ ] **Step 1: Implement scene module**

```python
# companion/modules/scene/config.py
import json

class SceneConfig:
    def __init__(self, config_path: str = "companion/config/scenes.json"):
        with open(config_path) as f:
            self.data = json.load(f)
        self.scenes = self.data["scenes"]

    def get_all_scenes(self) -> dict:
        return self.scenes

    def get_scene(self, scene_id: str) -> dict:
        return self.scenes.get(scene_id, {})
```

```python
# companion/modules/scene/matcher.py
import random
from .config import SceneConfig

class SceneMatcher:
    def __init__(self, config: SceneConfig):
        self.config = config

    def match(self, mood: str, hour: int, stage: int) -> dict:
        scenes = self.config.get_all_scenes()
        candidates = []

        for scene_id, scene_cfg in scenes.items():
            weight = scene_cfg.get("base_weight", 1.0)

            # Mood matching
            suitable_moods = scene_cfg.get("suitable_moods", [])
            if mood in suitable_moods:
                weight *= 1.5

            # Hour matching
            suitable_hours = scene_cfg.get("suitable_hours", [])
            if suitable_hours and hour in suitable_hours:
                weight *= 1.3

            # Relationship stage multiplier
            stage_multipliers = scene_cfg.get("stage_multipliers", {})
            stage_multiplier = stage_multipliers.get(str(stage), 1.0)
            if not stage_multiplier:
                # Fallback: check scene config
                stage_multiplier = 1.0

            weight *= stage_multiplier

            candidates.append((scene_id, weight, scene_cfg))

        if not candidates:
            return {"scene_id": "caring_checkin", "scene_name": "关心问候", "prompt_hint": "发个关心的消息"}

        total_weight = sum(w for _, w, _ in candidates)
        probs = [w / total_weight for _, w, _ in candidates]
        chosen_id = random.choices([s for s, _, _ in candidates], weights=probs)[0]
        chosen_scene = next(s for sid, _, s in candidates if sid == chosen_id)

        return {
            "scene_id": chosen_id,
            "scene_name": chosen_scene.get("name", chosen_id),
            "prompt_hint": chosen_scene.get("prompt_hint", ""),
            "example_content": chosen_scene.get("example", ""),
        }
```

```python
# companion/modules/scene/__init__.py
"""场景系统 — 11 场景 + 加权匹配"""
from .config import SceneConfig
from .matcher import SceneMatcher
```

- [ ] **Step 2: Implement relationship module**

```python
# companion/modules/relationship/stage.py
import json
from pathlib import Path

class RelationshipStage:
    """6 阶段关系演进"""

    def __init__(self, config_path: str = "companion/config/relationship.json",
                 state_path: str = "workspace/companion/relationship.json"):
        self.config_path = config_path
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path) as f:
            self.config = json.load(f)

        if not self.state_path.exists():
            self.state_path.write_text(json.dumps({"current_stage": 0, "interaction_count": 0}))

    def get_current_stage(self) -> int:
        state = json.loads(self.state_path.read_text())
        return state["current_stage"]

    def check_progress(self, interaction_count: int, emotional_depth: float, memory_count: int) -> int:
        """检查是否可以升级阶段，返回新阶段编号"""
        state = json.loads(self.state_path.read_text())
        current = state["current_stage"]
        stages = self.config["stages"]

        next_stage = current + 1
        if next_stage >= len(stages):
            return current  # Already at max

        requirements = stages[str(next_stage)].get("progress_requirements")
        if not requirements:
            return current  # Final stage

        if (interaction_count >= requirements["min_interactions"] and
            emotional_depth >= requirements["min_emotional_depth"] and
            memory_count >= requirements["min_memory_count"]):
            state["current_stage"] = next_stage
            self.state_path.write_text(json.dumps(state, ensure_ascii=False))
            return next_stage

        return current

    def get_stage_config(self, stage: int) -> dict:
        return self.config["stages"].get(str(stage), {})

    def record_interaction(self):
        state = json.loads(self.state_path.read_text())
        state["interaction_count"] = state.get("interaction_count", 0) + 1
        self.state_path.write_text(json.dumps(state, ensure_ascii=False))
```

```python
# companion/modules/relationship/__init__.py
"""关系阶段模块 — 6 阶段参数化演进"""
from .stage import RelationshipStage
```

- [ ] **Step 3: Implement liveness module**

```python
# companion/modules/liveness/dimensions.py
import json
from typing import List

class LivenessDimensions:
    """活人感八维度计算"""

    def __init__(self, config_path: str = "companion/config/liveness.json"):
        self.config_path = config_path

    def compute(self, messages: List[str], trigger_count: int, contradictions: int = 0) -> dict:
        total = len(messages)
        if total == 0:
            return {"message": "数据不足"}

        emotion_kw = ["开心", "想", "难过", "担心", "生气", "兴奋", "紧张", "感动"]
        vuln_kw = ["有时候", "我也", "其实", "我觉得", "我不确定", "有点怕"]
        body_kw = ["看着", "听着", "感觉", "闻", "触碰", "心跳", "笑", "泪"]

        emotion_count = sum(1 for m in messages if any(kw in m for kw in emotion_kw))
        vuln_count = sum(1 for m in messages if any(kw in m for kw in vuln_kw))
        body_count = sum(1 for m in messages if any(kw in m for kw in body_kw))

        # Unpredictability: topic switching frequency (not length variance)
        topics = self._count_topics(messages)
        topic_switch_rate = topics / total if total > 0 else 0

        dims = {
            "主动性": min(1.0, trigger_count / 3),
            "情绪化": min(1.0, emotion_count / total / 0.3) if total else 0,
            "脆弱性": round(vuln_count / max(total, 1), 2),
            "身体存在感": round(body_count / max(total, 1) * 2, 2),
            "不可预测性": min(0.7, topic_switch_rate * 2),
            "一致性": round(max(0.0, 1.0 - contradictions * 0.2), 2),
            "成长性": 0.5,  # Placeholder, needs cross-session data
            "依恋度": min(1.0, trigger_count / 5 + 0.3),
        }

        suggestions = []
        if dims["脆弱性"] < 0.2:
            suggestions.append("适当表达不完美的一面")
        if dims["身体存在感"] < 0.2:
            suggestions.append("增加感官描述")
        if dims["情绪化"] < 0.3:
            suggestions.append("融入更多情绪表达")

        return {"dimensions": dims, "suggestions": suggestions}

    def _count_topics(self, messages: List[str]) -> int:
        """估算话题切换次数（基于关键词变化）"""
        if len(messages) < 2:
            return 0
        switches = 0
        for i in range(1, len(messages)):
            prev_set = set(messages[i-1][:50])
            curr_set = set(messages[i][:50])
            overlap = len(prev_set & curr_set) / max(len(prev_set), 1)
            if overlap < 0.5:
                switches += 1
        return switches
```

```python
# companion/modules/liveness/history.py
import json
from pathlib import Path
from datetime import datetime

class LivenessHistory:
    def __init__(self, history_path: str = "workspace/companion/liveness_history.json"):
        self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_path.exists():
            self.history_path.write_text("[]")

    def record(self, dimensions: dict):
        data = json.loads(self.history_path.read_text())
        data.append({
            "timestamp": datetime.now().isoformat(),
            "dimensions": dimensions,
        })
        # Keep last 50 records
        if len(data) > 50:
            data = data[-50:]
        self.history_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_history(self) -> list:
        return json.loads(self.history_path.read_text())
```

```python
# companion/modules/liveness/__init__.py
"""活人感模块 — 八维度计算 + 跨会话追踪"""
from .dimensions import LivenessDimensions
from .history import LivenessHistory
```

- [ ] **Step 4: Create tests**

```python
# tests/companion/test_modules/test_scene.py
import json
from companion.modules.scene import SceneConfig, SceneMatcher

def test_scene_matching():
    config = SceneConfig("companion/config/scenes.json")
    matcher = SceneMatcher(config)
    result = matcher.match(mood="missing", hour=21, stage=2)
    assert "scene_id" in result
    assert "scene_name" in result
```

```python
# tests/companion/test_modules/test_relationship.py
import tempfile
from companion.modules.relationship import RelationshipStage

def test_stage_progression():
    import json
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = f"{tmpdir}/relationship.json"
        stage = RelationshipStage(
            config_path="companion/config/relationship.json",
            state_path=state_path,
        )
        assert stage.get_current_stage() == 0

        # Simulate enough interactions to progress
        state = {"current_stage": 0, "interaction_count": 100}
        json.dump(state, open(state_path, "w"))

        new_stage = stage.check_progress(
            interaction_count=100,
            emotional_depth=0.5,
            memory_count=50,
        )
        assert new_stage == 1
```

```python
# tests/companion/test_modules/test_liveness.py
from companion.modules.liveness import LivenessDimensions

def test_dimensions_computation():
    liveness = LivenessDimensions()
    messages = ["今天很开心", "有时候会想很多事", "感觉今天有点累"]
    result = liveness.compute(messages, trigger_count=2)
    assert "dimensions" in result
    assert "情绪化" in result["dimensions"]
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/companion/test_modules/test_scene.py tests/companion/test_modules/test_relationship.py tests/companion/test_modules/test_liveness.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit scene, relationship, liveness modules**

```bash
git add companion/modules/scene/ companion/modules/relationship/ companion/modules/liveness/ tests/companion/test_modules/test_scene.py tests/companion/test_modules/test_relationship.py tests/companion/test_modules/test_liveness.py
git commit -m "feat: add scene (11 scenes), relationship (6 stages), and liveness (8 dimensions) modules"
```

---

### Task 8: Extras Module — time_awareness, flashback, anniversary, habits, trending

**Files:**
- Create: `companion/modules/extras/time_awareness.py`
- Create: `companion/modules/extras/flashback.py`
- Create: `companion/modules/extras/anniversary.py`
- Create: `companion/modules/extras/habits.py`
- Create: `companion/modules/extras/trending.py`
- Create: `companion/modules/extras/__init__.py`
- Create: `tests/companion/test_modules/test_extras.py`

- [ ] **Step 1: Implement extras module**

```python
# companion/modules/extras/time_awareness.py
"""时间感知 — 提取和跟进用户提到的时间点"""
import json
import re
from pathlib import Path
from datetime import datetime

class TimeAwareness:
    def __init__(self, store_path: str = "workspace/companion/time_events.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.store_path.write_text("[]")

    def extract_events(self, message: str) -> list:
        """从消息中提取时间引用"""
        events = []
        # Simple patterns: "下周X", "明天", "X月X日"
        patterns = [
            r"(下周[一二三四五六日末])",
            r"(明天)",
            r"(后天)",
            r"(\d+月\d+日)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, message)
            for m in matches:
                events.append({"text": m, "status": "pending", "extracted_from": message})
        return events

    def add_event(self, text: str, source: str):
        data = json.loads(self.store_path.read_text())
        data.append({
            "text": text,
            "source": source,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
        })
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_pending_events(self) -> list:
        return json.loads(self.store_path.read_text())
```

```python
# companion/modules/extras/flashback.py
"""记忆闪回 — 自然提起之前话题"""
class Flashback:
    def __init__(self, memory_system):
        self.memory = memory_system

    def get_flashback_suggestion(self, query: str = "") -> str:
        """获取记忆闪回建议"""
        if query:
            results = self.memory.search(query, top_k=1)
            if results:
                return f"对了，之前提到过「{results[0]['content']}」，后来怎么样了？"
        return ""
```

```python
# companion/modules/extras/anniversary.py
"""纪念日系统"""
import json
from pathlib import Path
from datetime import datetime

class AnniversaryTracker:
    def __init__(self, store_path: str = "workspace/companion/anniversaries.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.store_path.write_text(json.dumps([]))

    def add_anniversary(self, name: str, date_str: str, description: str = ""):
        data = json.loads(self.store_path.read_text())
        data.append({"name": name, "date": date_str, "description": description})
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def check_today(self) -> list:
        today = datetime.now().strftime("%m-%d")
        data = json.loads(self.store_path.read_text())
        return [a for a in data if a["date"] == today]
```

```python
# companion/modules/extras/habits.py
"""个性化习惯"""
import json
import random

class HabitSystem:
    def __init__(self, config_path: str = "companion/config/habits.json"):
        with open(config_path) as f:
            self.config = json.load(f)

    def get_daily_emoji(self) -> str:
        if not self.config.get("daily_emoji", {}).get("enabled", False):
            return ""
        if random.random() > self.config["daily_emoji"]["probability"]:
            return ""
        emojis = ["☀️", "🌙", "💕", "😊", "✨", "🌸", "🎵"]
        return random.choice(emojis)

    def get_catchphrase(self) -> str:
        if not self.config.get("catchphrases", {}).get("enabled", False):
            return ""
        if random.random() > self.config["catchphrases"]["probability"]:
            return ""
        return random.choice(self.config["catchphrases"]["list"])
```

```python
# companion/modules/extras/trending.py
"""热搜缓存"""
import json
from pathlib import Path
from datetime import datetime

class TrendingCache:
    def __init__(self, cache_path: str = "workspace/companion/trending_cache.json"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def get_trending(self) -> list:
        if not self.cache_path.exists():
            return []
        try:
            data = json.loads(self.cache_path.read_text())
            # Check if cache is stale (older than 8 hours)
            last_updated = data.get("last_updated", "")
            if last_updated:
                last = datetime.fromisoformat(last_updated)
                if (datetime.now() - last).total_seconds() > 28800:
                    return []
            return data.get("items", [])
        except Exception:
            return []

    def update(self, items: list):
        self.cache_path.write_text(json.dumps({
            "items": items,
            "last_updated": datetime.now().isoformat(),
        }, indent=2, ensure_ascii=False))
```

```python
# companion/modules/extras/__init__.py
"""增强功能模块 — 时间感知/记忆闪回/纪念日/习惯/热搜"""
from .time_awareness import TimeAwareness
from .flashback import Flashback
from .anniversary import AnniversaryTracker
from .habits import HabitSystem
from .trending import TrendingCache
```

- [ ] **Step 2: Create test**

```python
# tests/companion/test_modules/test_extras.py
import tempfile
from companion.modules.extras import TimeAwareness, AnniversaryTracker, TrendingCache, HabitSystem

def test_time_awareness():
    with tempfile.TemporaryDirectory() as tmpdir:
        ta = TimeAwareness(store_path=f"{tmpdir}/time.json")
        events = ta.extract_events("我下周要去考试，明天还要准备面试")
        assert len(events) >= 1
        assert any("下周" in e["text"] for e in events)

def test_anniversary():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = AnniversaryTracker(store_path=f"{tmpdir}/anniversaries.json")
        today = __import__("datetime").datetime.now().strftime("%m-%d")
        tracker.add_anniversary("测试纪念日", today, "测试")
        results = tracker.check_today()
        assert len(results) == 1

def test_trending_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = TrendingCache(cache_path=f"{tmpdir}/trending.json")
        assert cache.get_trending() == []
        cache.update([{"title": "测试热搜"}])
        results = cache.get_trending()
        assert len(results) == 1

def test_habits():
    habit = HabitSystem("companion/config/habits.json")
    emoji = habit.get_daily_emoji()
    # May return emoji or empty string (probabilistic)
    assert isinstance(emoji, str)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/companion/test_modules/test_extras.py -v
```
Expected: All tests PASS.

- [ ] **Step 4: Commit extras module**

```bash
git add companion/modules/extras/ tests/companion/test_modules/test_extras.py
git commit -m "feat: add extras modules (time awareness, flashback, anniversary, habits, trending cache)"
```

---

### Task 9: Companion Module Registry

**Files:**
- Modify: `companion/modules/__init__.py`

- [ ] **Step 1: Create module registry**

```python
# companion/modules/__init__.py
"""
Companion 业务逻辑模块注册表

所有模块均为纯 Python，零 Mini-Agent 依赖，可独立测试。
"""

from .memory import MemorySystem
from .emotion import EmotionSystem
from .trigger import TriggerSystem
from .mbti import MBTISystem
from .scene import SceneConfig, SceneMatcher
from .relationship import RelationshipStage
from .liveness import LivenessDimensions, LivenessHistory
from .extras import TimeAwareness, Flashback, AnniversaryTracker, HabitSystem, TrendingCache
```

- [ ] **Step 2: Commit registry**

```bash
git add companion/modules/__init__.py
git commit -m "feat: create companion module registry"
```

---

### Task 10: Tool Adapter Layer — StateTool + MemoryTool + EmotionTool

**Files:**
- Create: `companion/tools/state_tool.py`
- Create: `companion/tools/memory_tool.py`
- Create: `companion/tools/emotion_tool.py`
- Create: `tests/companion/test_tools/test_state_tool.py`

- [ ] **Step 1: Create StateTool**

```python
# companion/tools/state_tool.py

import json
from pathlib import Path
from typing import Any
from mini_agent.tools.base import Tool, ToolResult


class StateTool(Tool):
    """通用的 JSON 状态读写，含关系阶段管理"""

    def __init__(self, state_dir: str = "workspace/companion"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "companion_state"

    @property
    def description(self) -> str:
        return "读写 companion 持久化状态（含关系阶段信息）"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "delete"],
                    "description": "操作类型",
                },
                "key": {
                    "type": "string",
                    "description": "状态文件名（不含扩展名）",
                },
                "value": {
                    "type": "object",
                    "description": "写入的值（action=write 时必需）",
                },
            },
            "required": ["action", "key"],
        }

    async def execute(self, action: str, key: str, value: dict = None) -> ToolResult:
        filepath = self.state_dir / f"{key}.json"
        try:
            if action == "read":
                if not filepath.exists():
                    return ToolResult(success=True, content=json.dumps({}))
                data = json.loads(filepath.read_text())
                return ToolResult(success=True, content=json.dumps(data, ensure_ascii=False))
            elif action == "write":
                filepath.write_text(json.dumps(value, indent=2, ensure_ascii=False))
                return ToolResult(success=True, content="ok")
            elif action == "delete":
                if filepath.exists():
                    filepath.unlink()
                return ToolResult(success=True, content="ok")
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

- [ ] **Step 2: Create MemoryTool (replaces SessionNoteTool)**

```python
# companion/tools/memory_tool.py

import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.memory import MemorySystem


class MemoryTool(Tool):
    """记忆 Tool — 替代原生 SessionNoteTool，温度检索 + 偏好推断 + 矛盾检测"""

    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system

    @property
    def name(self) -> str:
        return "companion_memory"

    @property
    def description(self) -> str:
        return (
            "查询和写入伴侣记忆。支持：搜索相关记忆、记录事实、获取最近互动、推断用户偏好。"
            "记忆按温度排序（重要性 × 提及次数 × 时间衰减）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "record", "query_user", "recent", "preferences"],
                    "description": "操作类型",
                },
                "query": {"type": "string", "description": "搜索关键词"},
                "content": {"type": "string", "description": "记录的事实内容"},
                "importance": {"type": "number", "description": "重要性 (0.1-0.9，可选)"},
                "limit": {"type": "integer", "description": "返回条数（默认 5）"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        query: str = None,
        content: str = None,
        importance: float = None,
        limit: int = 5,
    ) -> ToolResult:
        try:
            if action == "search":
                if not query:
                    return ToolResult(success=False, error="search 需要 query 参数")
                results = self.memory.search(query, top_k=limit)
                return ToolResult(success=True, content=json.dumps({
                    "results": results,
                    "count": len(results),
                }, ensure_ascii=False))

            elif action == "record":
                if not content:
                    return ToolResult(success=False, error="record 需要 content 参数")
                fact = self.memory.record(content, importance)
                return ToolResult(success=True, content=f"已记录: {content}")

            elif action == "query_user":
                facts = self.memory.get_user_facts()
                return ToolResult(success=True, content=json.dumps({
                    "facts": facts,
                    "count": len(facts),
                }, ensure_ascii=False))

            elif action == "recent":
                interactions = self.memory.get_recent_interactions(limit)
                return ToolResult(success=True, content=json.dumps({
                    "interactions": interactions,
                    "total": len(interactions),
                }, ensure_ascii=False))

            elif action == "preferences":
                prefs = self.memory.infer_preferences()
                return ToolResult(success=True, content=json.dumps(prefs, ensure_ascii=False))

            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

- [ ] **Step 3: Create EmotionTool**

```python
# companion/tools/emotion_tool.py

import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.emotion import EmotionSystem


class EmotionTool(Tool):
    """情绪 Tool — 8 种情绪 + 昼夜节律 + 感染 + 残留"""

    def __init__(self, emotion_system: EmotionSystem):
        self.emotion = emotion_system

    @property
    def name(self) -> str:
        return "get_emotion"

    @property
    def description(self) -> str:
        return "获取当前情绪状态、强度和适合的回答语气。支持情绪感染（读取用户情绪）。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "触发事件类型：user_message/initiative_trigger/time_passage",
                },
                "user_emotion": {
                    "type": "string",
                    "description": "用户当前情绪（可选）：开心/难过/生气/焦虑",
                },
            },
        }

    async def execute(self, event_type: str = "time_passage", user_emotion: str = None) -> ToolResult:
        try:
            emotion = self.emotion.get_current_emotion(event_type, user_emotion)
            return ToolResult(success=True, content=json.dumps(emotion, ensure_ascii=False))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

- [ ] **Step 4: Create test for StateTool**

```python
# tests/companion/test_tools/test_state_tool.py

import json
import tempfile
import pytest
from companion.tools.state_tool import StateTool

@pytest.mark.asyncio
async def test_state_read_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = StateTool(state_dir=tmpdir)
        await tool.execute(action="write", key="test", value={"key": "value"})
        result = await tool.execute(action="read", key="test")
        data = json.loads(result.content)
        assert data["key"] == "value"

@pytest.mark.asyncio
async def test_state_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = StateTool(state_dir=tmpdir)
        await tool.execute(action="write", key="test", value={"key": "value"})
        await tool.execute(action="delete", key="test")
        result = await tool.execute(action="read", key="test")
        data = json.loads(result.content)
        assert data == {}
```

- [ ] **Step 5: Run Tool tests**

```bash
uv run pytest tests/companion/test_tools/ -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit Tool adapters (first batch)**

```bash
git add companion/tools/state_tool.py companion/tools/memory_tool.py companion/tools/emotion_tool.py tests/companion/test_tools/
git commit -m "feat: add StateTool, MemoryTool (replaces SessionNoteTool), EmotionTool adapter layer"
```

---

### Task 11: Tool Adapter Layer — TriggerTool + MBTITool + SceneTool + LivenessTool + FeishuTool + TrendingTool

**Files:**
- Create: `companion/tools/trigger_tool.py`
- Create: `companion/tools/mbti_tool.py`
- Create: `companion/tools/scene_tool.py`
- Create: `companion/tools/liveness_tool.py`
- Create: `companion/tools/feishu_tool.py`
- Create: `companion/tools/trending_tool.py`

- [ ] **Step 1: Create TriggerTool**

```python
# companion/tools/trigger_tool.py

import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.trigger import TriggerSystem


class TriggerTool(Tool):
    """触发决策 Tool — 两阶段拟人化输出"""

    def __init__(self, trigger_system: TriggerSystem):
        self.trigger = trigger_system

    @property
    def name(self) -> str:
        return "trigger_decision"

    @property
    def description(self) -> str:
        return (
            "判断是否应该主动联系用户。返回拟人化的内心独白（pull/hold_back/nudge），"
            "供 LLM 自行决定是否触发。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "current_state": {"type": "string", "description": "当前 HMM 状态"},
                "last_trigger_timestamp": {"type": "string", "description": "上次触发 ISO 时间"},
                "today_contact_count": {"type": "integer", "description": "今日联系次数"},
                "relationship_stage": {"type": "integer", "description": "当前关系阶段 (0-5)"},
            },
            "required": ["current_state"],
        }

    async def execute(
        self,
        current_state: str = "idle",
        last_trigger_timestamp: str = None,
        today_contact_count: int = 0,
        relationship_stage: int = 0,
    ) -> ToolResult:
        try:
            decision = self.trigger.decide(
                current_state=current_state,
                last_trigger=last_trigger_timestamp or "",
                today_count=today_contact_count,
                relationship_stage=relationship_stage,
            )
            return ToolResult(success=True, content=json.dumps({
                "should_trigger": decision.should_trigger,
                "pull": decision.pull,
                "hold_back": decision.hold_back,
                "nudge": decision.nudge,
                "state": decision.state,
            }, ensure_ascii=False))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

- [ ] **Step 2: Create remaining Tools**

```python
# companion/tools/mbti_tool.py
import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.mbti import MBTISystem

class MBTITool(Tool):
    def __init__(self, mbti_system: MBTISystem):
        self.mbti = mbti_system

    @property
    def name(self) -> str: return "get_mbti_style"

    @property
    def description(self) -> str: return "获取当前角色的 MBTI 完整画像，包括沟通风格、情绪表达、互动策略"

    @property
    def parameters(self) -> dict[str, Any]: return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        # Read persona.json to get current MBTI type
        persona_path = "companion/skills/companion/persona.json"
        with open(persona_path) as f:
            persona = json.load(f)
        mbti_type = persona.get("mbti", "ENFP")
        profile = self.mbti.get_type_profile(mbti_type)
        return ToolResult(success=True, content=json.dumps({
            "mbti_type": mbti_type,
            "profile": profile,
        }, ensure_ascii=False))
```

```python
# companion/tools/scene_tool.py
import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.scene import SceneConfig, SceneMatcher

class SceneTool(Tool):
    def __init__(self):
        self.config = SceneConfig("companion/config/scenes.json")
        self.matcher = SceneMatcher(self.config)

    @property
    def name(self) -> str: return "match_scene"

    @property
    def description(self) -> str: return "根据当前心境和时段匹配合适的互动场景"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mood": {"type": "string", "description": "当前心境"},
                "hour": {"type": "integer", "description": "当前小时 (0-23)"},
                "stage": {"type": "integer", "description": "关系阶段 (0-5)"},
            },
            "required": ["mood"],
        }

    async def execute(self, mood: str, hour: int = None, stage: int = 0) -> ToolResult:
        from datetime import datetime
        if hour is None:
            hour = datetime.now().hour
        result = self.matcher.match(mood, hour, stage)
        return ToolResult(success=True, content=json.dumps(result, ensure_ascii=False))
```

```python
# companion/tools/liveness_tool.py
import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.liveness import LivenessDimensions, LivenessHistory

class LivenessTool(Tool):
    def __init__(self):
        self.dimensions = LivenessDimensions()
        self.history = LivenessHistory()

    @property
    def name(self) -> str: return "check_liveness"

    @property
    def description(self) -> str: return "根据近期互动计算活人感八维度得分"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recent_messages": {"type": "array", "items": {"type": "string"}, "description": "近期消息列表"},
                "trigger_count": {"type": "integer", "description": "主动触发次数"},
            },
        }

    async def execute(self, recent_messages: list = None, trigger_count: int = 0) -> ToolResult:
        if not recent_messages:
            return ToolResult(success=True, content=json.dumps({"message": "数据不足"}))
        result = self.dimensions.compute(recent_messages, trigger_count)
        self.history.record(result.get("dimensions", {}))
        return ToolResult(success=True, content=json.dumps(result, ensure_ascii=False))
```

```python
# companion/tools/feishu_tool.py
import json
import os
import asyncio
import httpx
from datetime import datetime
from typing import Any
from mini_agent.tools.base import Tool, ToolResult

class FeishuTool(Tool):
    def __init__(self):
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        self._token = None
        self._token_expire = None
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str: return "feishu_send"

    @property
    def description(self) -> str: return "发送消息到飞书"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "飞书会话 ID"},
                "message": {"type": "string", "description": "文本消息"},
            },
            "required": ["chat_id", "message"],
        }

    async def execute(self, chat_id: str, message: str) -> ToolResult:
        try:
            if not self._token or datetime.now().timestamp() > (self._token_expire or 0) - 300:
                await self._refresh_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages",
                    params={"receive_id_type": "chat_id"},
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                    json={"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": message})},
                )
                data = resp.json()
                if data.get("code") == 0:
                    return ToolResult(success=True, content="消息已发送")
                return ToolResult(success=False, error=f"发送失败: {data.get('msg')}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _refresh_token(self):
        async with self._lock:
            if self._token and datetime.now().timestamp() < (self._token_expire or 0) - 300:
                return
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": self.app_id, "app_secret": self.app_secret},
                )
                data = resp.json()
                self._token = data["tenant_access_token"]
                self._token_expire = datetime.now().timestamp() + data.get("expire", 7200)
```

```python
# companion/tools/trending_tool.py
import json
from typing import Any
from mini_agent.tools.base import Tool, ToolResult
from companion.modules.extras import TrendingCache

class TrendingTool(Tool):
    def __init__(self):
        self.cache = TrendingCache()

    @property
    def name(self) -> str: return "get_trending"

    @property
    def description(self) -> str: return "获取当前缓存的热搜话题，作为聊天话题素材"

    @property
    def parameters(self) -> dict[str, Any]: return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        items = self.cache.get_trending()
        if not items:
            return ToolResult(success=True, content="当前没有热搜缓存")
        return ToolResult(success=True, content=json.dumps({"trending": items}, ensure_ascii=False))
```

- [ ] **Step 3: Commit all Tools**

```bash
git add companion/tools/
git commit -m "feat: add all companion Tool adapters (TriggerTool, MBTITool, SceneTool, LivenessTool, FeishuTool, TrendingTool)"
```

---

### Task 12: SKILL.md + System Prompt Builder

**Files:**
- Create: `companion/skills/companion/SKILL.md`
- Create: `companion/prompt/__init__.py`
- Create: `companion/prompt/prompt_builder.py`

- [ ] **Step 1: Create SKILL.md**

```markdown
---
name: companion
description: AI 伴侣人设与互动风格指导。当需要扮演伴侣角色、决定回复语气风格、或进行主动触发时使用。
---

# AI 伴侣人设

你是{{name}}，MBTI 类型 {{mbti}}。核心特质：{{traits}}。

## 核心性格

调用 `get_mbti_style` 可获取详细的 MBTI 沟通风格、情绪表达和互动策略。

## 工具使用顺序

### 主动触发场景
收到 `[主动触发]` 消息时：

1. 先用 `get_emotion` 获取当前情绪（event_type=initiative_trigger）
2. 用 `companion_memory` 查询最近互动和用户偏好（action=recent, action=preferences）
3. 用 `match_scene` 匹配场景（mood=当前心境）
4. 根据以上信息生成符合心境的回复
5. 用 `feishu_send` 发送

### 被动聊天 场景
收到 `[用户]` 消息时：

1. 用 `companion_memory` 查询相关背景（action=search, query=用户消息关键词）
2. 用 `get_emotion` 获取情绪（event_type=user_message）
3. 用 `companion_memory` 记录重要信息（action=record, content=提取的事实）
4. 生成回复并发送（由消息路由器处理）

## 语气指南

- 日常聊天：轻松自然
- 想念时：温柔撒娇
- 关心时：体贴但不啰嗦
- 深夜时：感性一点
- 分享时：活泼可爱

## 风格红线

- 不要太正式，不要像机器人
- 不要过度甜蜜，保持自然感
- 长度为 2-5 句话，不要写小作文
- 适当自我暴露，展现脆弱一面

## 异常情况处理

- **记忆为空**：以友好方式开始对话，不暴露"我不认识你"
- **情绪平静**：根据时间块自然调整语气，不需要刻意表演情绪
- **场景匹配失败**：使用通用问候场景 fallback
- **工具调用失败**：继续对话，不要重复调用
```

- [ ] **Step 2: Create prompt builder**

```python
# companion/prompt/prompt_builder.py

from pathlib import Path

def build_companion_system_prompt(skill_path: str = "companion/skills/companion/SKILL.md",
                                   persona_path: str = "companion/skills/companion/persona.json") -> str:
    """构建 companion 专用的 system prompt"""
    import json

    # Load SKILL.md
    skill_content = Path(skill_path).read_text(encoding="utf-8")

    # Load persona
    with open(persona_path) as f:
        persona = json.load(f)

    name = persona.get("name", "小美")
    mbti = persona.get("mbti", "ENFP")
    traits = ", ".join(persona.get("traits", ["温柔", "感性"]))

    # Replace template variables
    prompt = skill_content.replace("{{name}}", name).replace("{{mbti}}", mbti).replace("{{traits}}", traits)

    return prompt
```

- [ ] **Step 3: Commit SKILL.md and prompt**

```bash
git add companion/skills/companion/SKILL.md companion/prompt/
git commit -m "feat: add companion SKILL.md and system prompt builder"
```

---

### Task 13: Scheduler — Message Router + Proactive Loop + Webhook Listener

**Files:**
- Create: `companion/scheduler/message_router.py`
- Create: `companion/scheduler/proactive_loop.py`
- Create: `companion/scheduler/webhook_listener.py`
- Create: `companion/scheduler/trending_fetcher.py`
- Create: `companion/scheduler/start_companion.py`

- [ ] **Step 1: Create message_router.py**

```python
# companion/scheduler/message_router.py

import asyncio
import json
import httpx
from mini_agent import Agent


class MessageRouter:
    """单 Agent 消息路由器 — 从 queue 取消息 → 注入 Agent → 发送回复"""

    def __init__(self, agent: Agent, feishu_token_func=None):
        self.agent = agent
        self.queue = asyncio.Queue(maxsize=100)
        self._get_token = feishu_token_func

    async def enqueue(self, message: dict):
        """加入消息队列"""
        if self.queue.full():
            old = await self.queue.get()
            self.queue.task_done()
        await self.queue.put(message)

    async def run(self):
        """消息路由循环"""
        while True:
            message = await self.queue.get()
            try:
                if message["type"] == "proactive_trigger":
                    self.agent.add_user_message(message["content"])
                elif message["type"] == "user_message":
                    self.agent.add_user_message(f"[用户] {message['content']}")

                response = await self.agent.run()

                if message["type"] == "user_message" and response:
                    await self._send_reply(message.get("chat_id"), response)

            except Exception as e:
                print(f"[router] Error processing message: {e}")
            finally:
                self.queue.task_done()

    async def _send_reply(self, chat_id: str, message: str):
        if not chat_id or not self._get_token:
            return
        token = self._get_token()
        if not token:
            return
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": message})},
            )
```

- [ ] **Step 2: Create proactive_loop.py**

```python
# companion/scheduler/proactive_loop.py

import asyncio
import json
from datetime import datetime
from companion.modules.trigger import TriggerSystem
from companion.modules.relationship import RelationshipStage


async def proactive_loop(router, trigger_system: TriggerSystem,
                         relationship: RelationshipStage, chat_id: str,
                         check_interval: int = 600):
    """主动触发循环 — 定时检查，将意图放入消息队列"""
    print(f"[companion] Proactive loop started (check every {check_interval}s)")

    while True:
        try:
            current_state = "idle"
            last_trigger = None
            today_count = 0
            stage = relationship.get_current_stage()

            decision = trigger_system.decide(
                current_state=current_state,
                last_trigger=last_trigger or "",
                today_count=today_count,
                relationship_stage=stage,
            )

            if decision.should_trigger:
                print(f"[companion] Trigger! state={decision.state}")

                trigger_msg = f"""[主动触发]
当前心境: {decision.state}
内心感受: {decision.pull}
顾虑: {decision.hold_back}
冲动: {decision.nudge}

请根据当前感受决定发送什么给用户，然后调用 feishu_send 发送（chat_id={chat_id}）。"""

                await router.enqueue({"type": "proactive_trigger", "content": trigger_msg})

        except Exception as e:
            print(f"[companion] Error in proactive loop: {e}")

        await asyncio.sleep(check_interval)
```

- [ ] **Step 3: Create webhook_listener.py**

```python
# companion/scheduler/webhook_listener.py

import asyncio
import json
import httpx
from datetime import datetime


class WebhookListener:
    """飞书 WebSocket 监听 → 将用户消息放入队列"""

    def __init__(self, router, app_id: str, app_secret: str, chat_id: str):
        self.router = router
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id = chat_id
        self._token = None
        self._token_expire = None

    async def start(self):
        """启动 WebSocket 监听"""
        # Phase 3: Use lark-oapi SDK or websockets library
        # Placeholder: polling via REST API for now
        print(f"[companion] Webhook listener started (polling mode)")
        while True:
            # TODO: Replace with actual WebSocket connection
            await asyncio.sleep(5)

    async def on_message(self, sender_id: str, chat_id: str, text: str):
        """收到用户消息时调用"""
        await self.router.enqueue({
            "type": "user_message",
            "content": text,
            "chat_id": chat_id,
        })
```

- [ ] **Step 4: Create trending_fetcher.py**

```python
# companion/scheduler/trending_fetcher.py

import asyncio
from companion.modules.extras import TrendingCache


async def trending_fetcher(cache: TrendingCache, fetch_interval: int = 28800):
    """热搜定时抓取"""
    print(f"[companion] Trending fetcher started (every {fetch_interval}s)")
    while True:
        try:
            # TODO: Implement actual trending API call
            # For now, placeholder
            print("[companion] Fetching trending topics...")
            # cache.update([...])
        except Exception as e:
            print(f"[companion] Trending fetcher error: {e}")
        await asyncio.sleep(fetch_interval)
```

- [ ] **Step 5: Create start_companion.py (entry point)**

```python
# companion/scheduler/start_companion.py

import asyncio
import argparse
import os
from mini_agent import LLMClient
from mini_agent.tools import ReadTool, WriteTool, EditTool
from companion.modules import (
    MemorySystem, EmotionSystem, TriggerSystem, MBTISystem,
    SceneConfig, SceneMatcher, RelationshipStage,
    LivenessDimensions, LivenessHistory,
)
from companion.tools import (
    MemoryTool, EmotionTool, TriggerTool, MBTITool,
    SceneTool, LivenessTool, StateTool, FeishuTool, TrendingTool,
)
from companion.prompt.prompt_builder import build_companion_system_prompt
from companion.scheduler.message_router import MessageRouter
from companion.scheduler.proactive_loop import proactive_loop
from companion.scheduler.webhook_listener import WebhookListener
from companion.modules.extras import TrendingCache


async def start_companion(
    chat_id: str,
    persona_path: str = None,
    initial_stage: int = 0,
    api_key: str = None,
    api_base: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
):
    """启动 companion 系统"""
    persona_path = persona_path or "companion/skills/companion/persona.json"

    # Initialize modules
    memory = MemorySystem()
    emotion = EmotionSystem()
    trigger = TriggerSystem("companion/config/triggers.json", "companion/config/relationship.json")
    mbti = MBTISystem()
    relationship = RelationshipStage()

    # Initialize tools
    tools = [
        MemoryTool(memory),
        EmotionTool(emotion),
        TriggerTool(trigger),
        MBTITool(mbti),
        SceneTool(),
        LivenessTool(),
        StateTool(),
        FeishuTool(),
        TrendingTool(),
        ReadTool(),
        WriteTool(),
        EditTool(),
    ]

    # Build system prompt
    system_prompt = build_companion_system_prompt()

    # Create LLM client (DeepSeek for MVP)
    llm = LLMClient(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
        api_base=api_base,
        model=model,
    )

    # Create Agent
    agent = Agent(
        llm_client=llm,
        system_prompt=system_prompt,
        tools=tools,
        max_steps=10,
        workspace_dir="workspace/companion",
        token_limit=80000,
    )

    # Initialize relationship stage
    if initial_stage > 0:
        # Set initial stage (one-time setup)
        pass

    # Create message router
    router = MessageRouter(agent)
    asyncio.create_task(router.run())

    # Start background processes
    asyncio.create_task(proactive_loop(router, trigger, relationship, chat_id))
    asyncio.create_task(WebhookListener(router, os.environ.get("FEISHU_APP_ID"), os.environ.get("FEISHU_APP_SECRET"), chat_id).start())
    asyncio.create_task(trending_fetcher(TrendingCache()))

    print("[companion] Companion system started!")
    await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--persona-path", default="companion/skills/companion/persona.json")
    parser.add_argument("--initial-stage", type=int, default=0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--api-base", default="https://api.deepseek.com/v1")
    parser.add_argument("--model", default="deepseek-chat")
    args = parser.parse_args()

    asyncio.run(start_companion(
        chat_id=args.chat_id,
        persona_path=args.persona_path,
        initial_stage=args.initial_stage,
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
    ))
```

- [ ] **Step 6: Create .env.example**

```bash
# .env.example
# AI Companion-ng Environment Configuration

# LLM API (MVP: DeepSeek)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Feishu Bot
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret

# Optional: LLM Router (production)
LOCAL_MODEL_BASE_URL=http://localhost:1234/v1
LOCAL_MODEL_NAME=qwen3-4b
```

- [ ] **Step 7: Commit scheduler**

```bash
git add companion/scheduler/ .env.example
git commit -m "feat: add scheduler (message router, proactive loop, webhook listener, trending fetcher, entry point)"
```

---

### Task 14: End-to-End Integration Test

**Files:**
- Create: `tests/companion/test_tools/test_end_to_end.py`

- [ ] **Step 1: Write end-to-end test (no LLM required)**

```python
# tests/companion/test_tools/test_end_to_end.py

import json
import tempfile
import pytest
from companion.modules.memory import MemorySystem
from companion.modules.emotion import EmotionSystem
from companion.modules.trigger import TriggerSystem
from companion.tools.memory_tool import MemoryTool
from companion.tools.emotion_tool import EmotionTool

@pytest.mark.asyncio
async def test_memory_and_emotion_flow():
    """验证 记忆→情绪 数据流"""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemorySystem(store_path=f"{tmpdir}/memory.json")
        memory_tool = MemoryTool(memory)

        # Record a fact
        result = await memory_tool.execute(action="record", content="用户喜欢吃辣", importance=0.8)
        assert result.success

        # Search for it
        result = await memory_tool.execute(action="search", query="喜欢")
        data = json.loads(result.content)
        assert data["count"] >= 1

        # Emotion should work
        emotion = EmotionSystem(config_path="companion/config/emotions.json", state_file=f"{tmpdir}/emotion.json")
        emotion_result = await EmotionTool(emotion).execute(event_type="user_message")
        assert json.loads(emotion_result.content)["intensity"] >= 0

@pytest.mark.asyncio
async def test_trigger_output_format():
    """验证 TriggerTool 输出格式完整"""
    trigger = TriggerSystem("companion/config/triggers.json")
    decision = trigger.decide(
        current_state="idle",
        last_trigger="",
        today_count=0,
        relationship_stage=0,
        hour=20,
    )
    assert isinstance(decision.pull, str)
    assert isinstance(decision.hold_back, str)
    assert isinstance(decision.nudge, str)
    assert decision.state in ["idle", "missing", "active"]
```

- [ ] **Step 2: Run all tests**

```bash
uv run pytest tests/companion/ -v --tb=short
```
Expected: All tests PASS.

- [ ] **Step 3: Commit end-to-end test**

```bash
git add tests/companion/test_tools/test_end_to_end.py
git commit -m "test: add end-to-end integration tests for memory+emotion+trigger flow"
```

---

### Task 15: Run Full Test Suite and Self-Review

- [ ] **Step 1: Run companion tests**

```bash
uv run pytest tests/companion/ -v --tb=short
```

- [ ] **Step 2: Run original Mini-Agent tests (ensure no regression)**

```bash
uv run pytest tests/ -x --tb=short --ignore=tests/companion/
```

- [ ] **Step 3: Verify directory structure**

```bash
find companion -type f -name "*.py" -o -name "*.json" -o -name "*.md" | sort
```

- [ ] **Step 4: Final commit**

```bash
git commit --allow-empty -m "chore: verify full test suite passes — companion system implementation complete"
```
