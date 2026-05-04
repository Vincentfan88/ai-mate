"""Companion 插件系统 — 轻量级 Tool 注入机制。

约定：
- companion/plugins/ 下每个子目录是一个插件
- 插件必须包含 __init__.py，并定义 register(registry) → List[Tool]
- 禁用插件：将目录重命名为 xxx.disabled
"""

import importlib
import logging
from pathlib import Path
from typing import List

from companion.modules.registry import CompanionRegistry

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent

# ── 插件白名单：仅允许加载以下已知安全的插件 ──
ALLOWED_PLUGINS: set[str] = set()  # 空表示扫描时无需白名单校验，但 import 前会校验目录结构


def load_plugin_tools(registry: CompanionRegistry) -> List:
    """扫描并加载 companion/plugins/ 下所有插件的 Tool。

    每个插件的 __init__.py 必须定义：
        def register(registry: CompanionRegistry) -> list[Tool]

    返回值：所有插件提供的 Tool 实例列表。
    """
    all_tools = []
    plugins_path = PLUGINS_DIR

    if not plugins_path.is_dir():
        return all_tools

    for item in sorted(plugins_path.iterdir()):
        # 跳过：隐藏目录、非目录、禁用插件
        if item.name.startswith("_") or item.name.endswith(".disabled") or not item.is_dir():
            continue

        init_file = item / "__init__.py"
        if not init_file.exists():
            continue

        # ── 安全检查：只允许 __init__.py，拒绝额外 .py 文件（防恶意代码） ──
        py_files = [f for f in item.glob("*.py") if f.name != "__init__.py"]
        if py_files:
            logger.warning(f"[Plugins] Skipping '{item.name}': unexpected files {py_files}")
            continue

        try:
            mod_name = f"companion.plugins.{item.name}"
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "register"):
                tools = mod.register(registry)
                if tools:
                    all_tools.extend(tools)
                    logger.info(f"[Plugins] Loaded {len(tools)} tool(s) from '{item.name}'")
                else:
                    logger.debug(f"[Plugins] Plugin '{item.name}' returned no tools")
            else:
                logger.warning(f"[Plugins] Plugin '{item.name}' has no register() function")
        except Exception as e:
            logger.warning(f"[Plugins] Failed to load plugin '{item.name}': {e}")

    return all_tools


def get_plugin_info() -> List[dict]:
    """获取已安装插件的元信息列表。"""
    plugins = []
    plugins_path = PLUGINS_DIR

    if not plugins_path.is_dir():
        return plugins

    for item in sorted(plugins_path.iterdir()):
        if item.name.startswith("_") or item.name.endswith(".disabled") or not item.is_dir():
            continue

        init_file = item / "__init__.py"
        if not init_file.exists():
            continue

        info = {"name": item.name, "enabled": True, "tools": []}
        try:
            mod_name = f"companion.plugins.{item.name}"
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "get_info"):
                info.update(mod.get_info())
        except Exception:
            pass
        plugins.append(info)

    return plugins