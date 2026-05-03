# ai-mate

AI 伙伴系统 v2.0 — 拥有"活人感"的 AI 伙伴，支持 16 种 MBTI 人格、飞书 Bot 集成和 Web UI。

[中文](#中文) | [English](#english)

---

## 中文

### 项目简介

ai-mate 是一个基于 Mini-Agent 框架的 AI 伙伴系统。它将 24K 行 Flask 系统的"活人感"能力迁移到轻量异步 Agent loop 上，保留全部核心能力：

- **16 MBTI 人格** — 每种人格有独立的说话风格、情绪表达和场景适配
- **活人感八维度** — 自发表情、主动开启、情感深度、场景适配等 8 个维度的"像人"评分
- **HMM 7 状态主动触发** — 基于隐马尔可夫模型的对话状态机，在恰当时机主动开口
- **情绪系统** — 8 情绪 + 昼夜节律 + 情绪感染 + 时间衰减
- **记忆系统** — L1 事实库 + L2+ 偏好推断 + 矛盾检测
- **场景匹配** — 基于心境、时段、关系上下文的加权场景推荐
- **飞书 Bot** — WebSocket 长连接，可在飞书群聊中运行
- **角色隔离** — 多个角色共享同一个系统，但记忆、状态、偏好完全隔离
- **Web UI** — FastAPI Web 界面

### 快速开始

#### 1. 环境要求

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器（推荐）

#### 2. 安装

```bash
git clone https://github.com/YOUR_USERNAME/ai-mate.git
cd ai-mate
uv sync
```

#### 3. 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM API 密钥
```

支持任何兼容 OpenAI API 格式的模型服务（DeepSeek、SiliconFlow 等）。

#### 4. 运行

```bash
# Web UI 模式（推荐）
uvicorn companion.webui.server:app --host 0.0.0.0 --port 8080
# 打开浏览器访问 http://localhost:8080

# CLI 模式
python -m companion.cli                        # 默认 ENFP
python -m companion.cli --mbti INTJ            # 指定 MBTI
python -m companion.cli --persona default      # 指定人格

# launchd 服务（macOS 生产部署）
launchctl start com.ai-mate.webui
```

### 架构概览

```
ai-mate/
├── mini_agent/              # Mini-Agent 框架（上游依赖）
├── companion/
│   ├── modules/             # 核心业务模块
│   │   ├── memory/          # 记忆系统（检索 + 偏好推断）
│   │   ├── emotion/         # 情绪（8情绪 + 昼夜节律）
│   │   ├── trigger/         # 主动触发（HMM 7状态）
│   │   ├── mbti/            # MBTI 16类型画像
│   │   ├── scene/           # 场景加权匹配
│   │   ├── liveness/        # 活人感八维度
│   │   └── extras/          # 时间管理/习惯/热搜
│   ├── webui/               # Web 界面（FastAPI）
│   ├── agent/               # Mini-Agent 集成层
│   ├── plugins/             # 插件系统（可扩展）
│   └── cli.py               # CLI 入口
├── tests/                   # 测试（296 passed）
└── docs/                    # 设计文档
```

### 测试

```bash
python -m pytest tests/companion/ -v --tb=short
# 296 passed, 0 failed
```

### 设计文档

- [完整设计](docs/superpowers/specs/2026-04-30-ai-mate-design.md)
- [实现计划](docs/superpowers/specs/2026-04-30-ai-mate-implementation.md)
- [飞书集成设计](docs/superpowers/specs/2026-05-01-ai-mate-feishu-integration.md)

---

## English

### Overview

ai-mate is an AI mate system built on the Mini-Agent framework. It ported the "aliveness" capabilities from a 24K-line Flask system into a lightweight async Agent loop, preserving all core features:

- **16 MBTI Personalities** — Each with distinct speaking style, emotional expression, and scene adaptation
- **8-Dimension Liveness** — Spontaneous expression, initiative, emotional depth, scene matching, and more
- **HMM 7-State Trigger** — Hidden Markov Model dialog state machine for natural conversation timing
- **Emotion System** — 8 emotions + circadian rhythm + emotional contagion + temporal decay
- **Memory System** — L1 facts + L2+ preference inference + contradiction detection
- **Scene Matching** — Context-aware weighted scene recommendation
- **Feishu Bot** — WebSocket long-running connection for Feishu group chat integration
- **Persona Isolation** — Multiple characters share one system with fully isolated memory and state
- **Web UI** — FastAPI web interface

### Quick Start

#### 1. Requirements

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

#### 2. Install

```bash
git clone https://github.com/YOUR_USERNAME/ai-mate.git
cd ai-mate
uv sync
```

#### 3. Configure

```bash
cp .env.example .env
# Edit .env with your LLM API key
```

Supports any OpenAI-compatible API service (DeepSeek, SiliconFlow, etc.).

#### 4. Run

```bash
# Web UI mode (recommended)
uvicorn companion.webui.server:app --host 0.0.0.0 --port 8080
# Open http://localhost:8080 in browser

# CLI mode
python -m companion.cli                        # default ENFP
python -m companion.cli --mbti INTJ            # specify MBTI
python -m companion.cli --persona default      # specify persona

# launchd service (macOS production deployment)
launchctl start com.ai-mate.webui
```

### Tests

```bash
python -m pytest tests/companion/ -v --tb=short
# 296 passed, 0 failed
```

---

## License

This project is dual-licensed:
- **AGPL-3.0** — for personal, educational, and non-commercial use (see [LICENSE](LICENSE))
- **Commercial license** — contact the author for business use without AGPL restrictions

Copyright (c) 2025 MiniMax (upstream Mini-Agent, MIT)
Copyright (c) 2026 Vincent Fan
