# Agent 生产环境指南

> 从 Demo 到生产的完整进阶指南

## 目录

- [1. Demo功能实现](#1-demo功能)
- [2. 可升级方向](#2-可升级方向)
- [3. 生产部署](#3-生产部署)

---

## 1. Demo功能实现

本项目是**教学级 Demo**，展示了 Agent 的核心概念和执行链路。要达到生产级别，还需要处理大量复杂问题。

### 我们实现的（Demo 级别）

| 功能                  | Demo 实现                   |
| --------------------- | --------------------------- |
| **上下文管理** | ✅ 通过SessionNoteTool，以文件存储简单实现了持久化；接近上下文窗口上限时，做摘要的简单处理 |
| **工具调用**          | ✅ 基础 Read/Write/Edit/Bash |
| **错误处理**          | ✅ 基础异常捕获              |
| **日志**              | ✅ 简单 print 输出           |


## 2. 可升级方向

### 2.1 高级上下文管理

- 引入分布式文件系统，将上下文持久化统一管理和备份
- 使用更精确的方式计算Token数
- 消息压缩时引入更多策略，包括保留最近N条、保留固定元信息、总结Prompt调优、引入召回系统等

### 2.2 模型 Fallback 机制

当前固定使用单一模型 (MiniMax-M2)，失败时会直接报错。

- 引入模型池，通过配置更多的模型账号来提高可用性
- 对模型池引入自动健康检测、故障摘除、熔断等策略

### 2.3 模型幻觉检测与修正

当前直接信任模型输出，无验证机制

- 对部分工具调用的入参做安全性检查，防止高危动作
- 对部分工具调用的结果做反思，检测是否合理

## 3. 生产部署

### 3.1 容器化部署建议

我们推荐使用 K8s/Docker 环境做 Agent 的部署。容器化部署有以下优势：

- **资源隔离**：每个 Agent 实例运行在独立的容器中，互不干扰
- **弹性扩展**：根据负载自动调整实例数量
- **版本管理**：便于快速回滚和灰度发布
- **环境一致性**：开发、测试、生产环境完全一致

### 3.2 资源限制配置

#### 3.2.1 CPU与内存限制

为防止 Agent 占用过多 CPU/MEM 资源影响宿主机，必须设置 CPU和 限制：

**Docker 配置示例**：
```yaml
# docker-compose.yml
services:
  agent:
    image: agent-demo:latest
    deploy:
      resources:
        limits:
          cpus: '2.0'      # 最多使用 2 个 CPU 核心
          memory: 2G       # 最多使用 2GB 内存
        reservations:
          cpus: '0.5'      # 保证至少 0.5 个核心
          memory: 512M     # 保证至少 512MB
```

#### 3.2.2 磁盘限制

Agent 可能会产生大量临时文件、日志文件，需要限制磁盘使用：

**Docker Volume 配置**：
```yaml
# docker-compose.yml
services:
  agent:
    volumes:
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1G         # 临时文件最多 1GB
      - type: volume
        source: agent-data
        target: /app/data
        volume:
          driver_opts:
            size: 5G       # 数据卷最多 5GB
```


### 3.3 Linux 账号权限限制

#### 3.3.1 最小权限原则

**永远不要以 root 用户运行 Agent**，这会带来严重的安全风险。

**Dockerfile 最佳实践**：
```dockerfile
FROM python:3.11-slim

# 安装必要的系统工具
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# 创建非特权用户
RUN groupadd -r agent && useradd -r -g agent agent

# 设置工作目录
WORKDIR /app

# 方案1：从 Git 仓库克隆（适用于公开仓库）
RUN git clone https://github.com/MiniMax-AI/agent-demo.git . && \
    chown -R agent:agent /app

# 方案2：从本地复制代码（适用于私有部署）
# COPY --chown=agent:agent . /app

# 切换到非特权用户后安装依赖
USER agent

# 使用 uv 同步依赖
RUN uv sync

# 启动应用
CMD ["uv", "run", "python", "main.py"]
```

#### 3.3.2 文件系统权限

限制 Agent 只能访问必要的目录：

```bash
# 创建受限的工作目录
mkdir -p /app/workspace
chown agent:agent /app/workspace
chmod 750 /app/workspace  # 所有者读写执行，组只读执行

# 限制敏感目录的访问
chmod 700 /etc/agent      # 配置目录只有所有者能访问
chmod 600 /etc/agent/*.yaml  # 配置文件只有所有者能读写
```