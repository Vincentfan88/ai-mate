# 开发指南


## 目录

- [开发指南](#开发指南)
  - [目录](#目录)
  - [1. 项目架构](#1-项目架构)
  - [2. 基础使用](#2-基础使用)
    - [2.1 交互式命令](#21-交互式命令)
    - [2.2 已集成的 MCP 工具](#22-已集成的-mcp-工具)
      - [Memory - 知识图谱记忆系统](#memory---知识图谱记忆系统)
      - [MiniMax Search - 网页搜索与浏览](#minimax-search---网页搜索与浏览)
  - [3. 扩展能力](#3-扩展能力)
    - [3.1 添加自定义工具](#31-添加自定义工具)
      - [步骤](#步骤)
      - [示例](#示例)
    - [3.2 添加 MCP 工具](#32-添加-mcp-工具)
    - [3.3 自定义存储](#33-自定义存储)
    - [3.4 初始化 Claude Skills（推荐）](#34-初始化-claude-skills推荐)
    - [3.5 添加新的Skill](#35-添加新的skill)
    - [3.6 自定义系统提示词](#36-自定义系统提示词)
      - [可自定义的内容](#可自定义的内容)
  - [4. 故障排查](#4-故障排查)
    - [4.1 常见问题](#41-常见问题)
      - [API 密钥配置错误](#api-密钥配置错误)
      - [依赖安装失败](#依赖安装失败)
      - [MCP 工具加载失败](#mcp-工具加载失败)
    - [4.2 调试技巧](#42-调试技巧)
      - [启用详细日志](#启用详细日志)
      - [使用 Python 调试器](#使用-python-调试器)
      - [检查工具调用](#检查工具调用)

---

## 1. 项目架构

```
mini-agent/
├── mini_agent/              # 核心源代码
│   ├── agent.py             # 主 Agent 循环
│   ├── llm.py               # LLM 客户端
│   ├── config.py            # 配置加载
│   └── tools/               # 工具实现
│       ├── base.py          # 工具基类
│       ├── file_tools.py    # 文件工具
│       ├── bash_tool.py     # Bash 工具
│       ├── note_tool.py     # 会话笔记工具
│       ├── mcp_loader.py    # MCP 加载器
│       ├── skill_loader.py  # 技能加载器
│       └── skill_tool.py    # 技能工具
├── tests/                   # 测试代码
├── skills/                  # Claude 技能（子模块）
├── docs/                    # 文档
├── workspace/               # 工作目录
├── main.py                  # 交互式入口
└── pyproject.toml           # 项目配置
```

## 2. 基础使用

### 2.1 交互式命令

在交互模式下运行 Agent（`python main.py`）时，可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/exit`, `/quit`, `/q` | 退出 Agent 并显示会话统计信息 |
| `/help` | 显示帮助信息和可用命令 |
| `/clear` | 清除消息历史并开始新会话 |
| `/history` | 显示当前会话的消息数量 |
| `/stats` | 显示会话统计信息（步数、工具调用、使用的 Token） |

### 2.2 已集成的 MCP 工具

本项目预配置了以下 MCP（模型上下文协议）工具，可以扩展 Agent 的能力：

#### Memory - 知识图谱记忆系统

**功能**：基于图数据库提供长期记忆存储和检索

**状态**：默认启用

**配置**：无需 API Key，开箱即用

**能力**：
- 跨会话存储和检索信息
- 从对话中构建知识图谱
- 对存储的记忆进行语义搜索

---

#### MiniMax Search - 网页搜索与浏览

**功能**：提供三个强大的工具：
- `search` - 网页搜索功能
- `parallel_search` - 并行执行多个搜索
- `browse` - 智能网页浏览和内容提取

**状态**：默认禁用，需要配置后启用

**配置示例**：

```json
{
  "mcpServers": {
    "minimax_search": {
      "disabled": false,
      "env": {
        "JINA_API_KEY": "your-jina-api-key",
        "SERPER_API_KEY": "your-serper-api-key",
        "MINIMAX_API_KEY": "your-minimax-token"
      }
    }
  }
}
```

## 3. 扩展能力

### 3.1 添加自定义工具

#### 步骤

1.  在 `mini_agent/tools/` 下创建新的工具文件。
2.  继承 `Tool` 基类。
3.  实现必需的属性和方法。
4.  在 Agent 初始化时注册工具。

#### 示例

```python
# mini_agent/tools/my_tool.py
from mini_agent.tools.base import Tool, ToolResult
from typing import Dict, Any

class MyTool(Tool):
    @property
    def name(self) -> str:
        """工具的唯一名称。"""
        return "my_tool"
    
    @property
    def description(self) -> str:
        """帮助 LLM 理解工具用途的描述。"""
        return "我的自定义工具，用于做一些有用的事情"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """OpenAI 函数调用格式的参数模式。"""
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "第一个参数"
                },
                "param2": {
                    "type": "integer",
                    "description": "第二个参数",
                    "default": 10
                }
            },
            "required": ["param1"]
        }
    
    async def execute(self, param1: str, param2: int = 10) -> ToolResult:
        """
        工具的主要逻辑。
        
        Args:
            param1: 第一个参数。
            param2: 第二个参数，有默认值。
        
        Returns:
            一个 ToolResult 对象。
        """
        try:
            # 在此实现你的逻辑
            result = f"处理了 {param1}，param2={param2}"
            
            return ToolResult(
                success=True,
                content=result
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content=f"错误: {str(e)}"
            )

# 在 main.py 或 agent 初始化代码中
from mini_agent.tools.my_tool import MyTool

# 创建 Agent 时添加新工具
tools = [
    ReadTool(workspace_dir),
    WriteTool(workspace_dir),
    MyTool(),  # 添加你的自定义工具
]

agent = Agent(
    llm=llm,
    tools=tools,
    max_steps=50
)
```

### 3.2 添加 MCP 工具

编辑 `mcp.json` 以添加新的 MCP 服务器：

```json
{
  "mcpServers": {
    "my_custom_mcp": {
      "description": "我的自定义 MCP 服务器",
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@my-org/my-mcp-server"],
      "env": {
        "API_KEY": "your-api-key"
      },
      "disabled": false,
      "notes": {
        "description": "这是一个自定义 MCP 服务器。",
        "api_key_url": "https://example.com/api-keys"
      }
    }
  }
}
```

### 3.3 自定义存储

替换 `SessionNoteTool` 的存储实现：

```python
# 当前实现：JSON 文件
class SessionNoteTool:
    def __init__(self, memory_file: str = "./workspace/.agent_memory.json"):
        self.memory_file = Path(memory_file)
    
    async def _save_notes(self, notes: List[Dict]):
        with open(self.memory_file, 'w') as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

# 扩展示例：PostgreSQL
class PostgresNoteTool(Tool):
    def __init__(self, db_url: str):
        self.db = PostgresDB(db_url)
    
    async def _save_notes(self, notes: List[Dict]):
        await self.db.execute(
            "INSERT INTO notes (content, category, timestamp) VALUES ($1, $2, $3)",
            notes
        )

# 扩展示例：向量数据库
class MilvusNoteTool(Tool):
    def __init__(self, milvus_host: str):
        self.vector_db = MilvusClient(host=milvus_host)
    
    async def _save_notes(self, notes: List[Dict]):
        # 生成嵌入向量
        embeddings = await self.get_embeddings([n["content"] for n in notes])
        
        # 存储到向量数据库
        await self.vector_db.insert(
            collection="agent_notes",
            data=notes,
            embeddings=embeddings
        )
```

### 3.4 初始化 Claude Skills（推荐）

本项目通过 git submodule 集成了 Claude 官方技能库。首次克隆后需要初始化：

```bash
# 初始化子模块
git submodule update --init --recursive
```

Skills 提供了 20 多种专业能力，让 Agent 像专业人士一样工作：

- 📄 **文档处理**：创建和编辑 PDF、DOCX、XLSX、PPTX
- 🎨 **设计创作**：生成艺术作品、海报、GIF 动画
- 🧪 **开发与测试**：Web 自动化测试（Playwright）、MCP 服务器开发
- 🏢 **企业应用**：内部沟通、品牌指南、主题定制

✨ **这是本项目的核心亮点之一。** 详细信息请参见下面的"配置 Skills"部分。

**更多信息：**
- [Claude Skills 官方文档](https://github.com/anthropics/anthropic-quickstarts/tree/main/claude-skills)
- [Anthropic 博客：为真实世界装备智能体](https://www.anthropic.com/news/equipping-agents-for-the-real-world)

### 3.5 添加新的Skill

创建自定义Skill：

```bash
# 在 skills/ 下创建新的技能目录
mkdir skills/my-custom-skill
cd skills/my-custom-skill

# 创建 SKILL.md 文件
cat > SKILL.md << 'EOF'
---
name: my-custom-skill
description: 我的自定义技能，用于处理特定任务。
---

# 概述

此技能提供以下功能：
- 功能 1
- 功能 2

# 使用方法

1. 第一步...
2. 第二步...

# 最佳实践

- 实践 1
- 实践 2

# 常见问题

问：问题 1
答：答案 1
EOF
```

新技能将自动被 Agent 加载并识别。

### 3.6 自定义系统提示词

系统提示词（`system_prompt.md`）定义了 Agent 的行为、能力和工作指南。你可以自定义它以适应特定的使用场景。

#### 可自定义的内容

1. **核心能力**：添加或修改工具描述
2. **工作指南**：定义自定义工作流程和最佳实践
3. **领域专业知识**：添加特定领域的专业知识
4. **沟通风格**：调整 Agent 与用户的交互方式
5. **任务优先级**：设置任务处理方式的偏好

修改 `system_prompt.md` 后，记得重启 Agent 以应用更改

## 4. 故障排查

### 4.1 常见问题

#### API 密钥配置错误

```bash
# 错误消息
Error: Invalid API key

# 解决方案
1. 检查 `config.yaml` 中的 API 密钥是否正确。
2. 确保没有多余的空格或引号。
3. 验证 API 密钥是否已过期。
```

#### 依赖安装失败

```bash
# 错误消息
uv sync failed

# 解决方案
1. 更新 uv 到最新版本：`uv self update`
2. 清除缓存：`uv cache clean`
3. 重新尝试同步：`uv sync`
```

#### MCP 工具加载失败

```bash
# 错误消息
Failed to load MCP server

# 解决方案
1. 检查 `mcp.json` 中的配置是否正确。
2. 确保已安装 Node.js（大多数 MCP 工具需要）。
3. 验证是否已配置所需的 API 密钥。
4. 查看详细日志：`pytest tests/test_mcp.py -v -s`
```

### 4.2 调试技巧

#### 启用详细日志

```python
# 在 main.py 或测试文件的开头
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

#### 使用 Python 调试器

```python
# 在代码中设置断点
import pdb; pdb.set_trace()

# 或使用 ipdb 获得更好的体验
import ipdb; ipdb.set_trace()
```

#### 检查工具调用

```python
# 在 Agent 中添加日志以查看工具交互
logger.debug(f"工具调用: {tool_call.name}")
logger.debug(f"工具参数: {tool_call.arguments}")
logger.debug(f"工具结果: {result.content[:200]}")
```

