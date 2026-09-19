#!/usr/bin/env python3
"""
Codebase Context Packer for Gemini Web & LLMs.
Packs project source files and instructions into a clean Markdown prompt
suitable for pasting directly into Gemini Web (gemini.google.com).
"""

from __future__ import annotations
import os
import sys
import subprocess
from datetime import datetime
from typing import List, Optional, Set

DEFAULT_CORE_FILES = [
    "portfolio_engine.py",
    "storage.py",
    "market_data.py",
    "web_app.py",
    "main.py",
    "cli.py",
    "README.md",
]

IGNORE_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "node_modules",
}

IGNORE_EXTS: Set[str] = {
    ".pyc",
    ".db",
    ".db-shm",
    ".db-wal",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".zip",
    ".tar",
    ".gz",
}


def get_project_tree(root_dir: str = ".") -> str:
    """Generate a clean ASCII file tree of the project."""
    tree_lines: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # In-place modify dirnames to skip ignored dirs
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        rel_dir = os.path.relpath(dirpath, root_dir)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        indent = "  " * depth

        if rel_dir != ".":
            tree_lines.append(f"{indent}📁 {os.path.basename(dirpath)}/")

        for f in sorted(filenames):
            ext = os.path.splitext(f)[1].lower()
            if ext in IGNORE_EXTS or f.endswith(".tmp") or f == "ai_task_context.md":
                continue
            tree_lines.append(f"{indent}  📄 {f}")

    return "\n".join(tree_lines)


def copy_to_clipboard(text: str) -> bool:
    """Attempt to copy text to system clipboard across Wayland, X11, and macOS."""
    commands = [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["pbcopy"],
    ]
    for cmd in commands:
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            p.communicate(input=text.encode("utf-8"), timeout=5)
            if p.returncode == 0:
                return True
        except (FileNotFoundError, Exception):
            continue
    return False


def build_pack_markdown(
    task_desc: str,
    included_files: Optional[List[str]] = None,
    include_all: bool = False,
    root_dir: str = "."
) -> str:
    """Build the complete Markdown prompt with project context and instructions."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine files to read
    if include_all:
        target_files = []
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for f in sorted(filenames):
                ext = os.path.splitext(f)[1].lower()
                if ext in IGNORE_EXTS or f == "ai_task_context.md" or f.endswith(".tmp"):
                    continue
                rel_path = os.path.relpath(os.path.join(dirpath, f), root_dir)
                target_files.append(rel_path)
    elif included_files:
        target_files = included_files
    else:
        target_files = [f for f in DEFAULT_CORE_FILES if os.path.exists(os.path.join(root_dir, f))]

    file_contents: List[str] = []
    file_stats: List[str] = []
    total_lines = 0

    for fpath in target_files:
        full_path = os.path.join(root_dir, fpath)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.count("\n") + (1 if content else 0)
            total_lines += lines
            file_stats.append(f"- `{fpath}` ({lines} 行, {len(content):,} 字符)")

            # Format extension for syntax highlighting
            ext = os.path.splitext(fpath)[1].lstrip(".")
            lang = ext if ext in ("py", "js", "html", "css", "json", "sh", "md") else ""
            file_contents.append(f"### 📄 文件: `{fpath}`\n```{lang}\n{content}\n```\n")
        except Exception as e:
            file_stats.append(f"- `{fpath}` (读取失败: {e})")

    file_tree = get_project_tree(root_dir)

    md = f"""# 🚀 项目上下文与开发需求任务单 (AI Task Context)

> **生成时间**: {now_str}  
> **目标模型**: Google Gemini (网页端 / gemini.google.com)  
> **代码库规模**: {len(target_files)} 个核心文件，共 {total_lines:,} 行代码

---

## 🎯 任务目标与需求描述 (Task Requirement)

{task_desc.strip() if task_desc else "请阅读下方的项目代码库，全面分析当前架构，并就系统功能完善、性能优化及代码重构提出具体的改进方案与实现代码。"}

---

## 📋 给网页端 Gemini 的输出规范要求 (Output Instructions)

作为专业资深的 Python & 金融量化全栈工程师，在输出方案时请遵循以下原则：

1. **精准定位与即插即用 (Drop-in Replacement)**：
   - 本地将使用轻量 Agent 进行精准替换与命令执行。
   - 请明确标明被修改的文件名（例如 `portfolio_engine.py` 或 `web_app.py`）。
   - 提供**完整的函数替换块**或**清晰的搜索替换对 (Search & Replace)**，避免模棱两可的代码省略（如避免使用 `// 其余代码保持不变...` 导致无法直接定位）。

2. **保持现有架构与设计风格**：
   - 保持原有的抽象存储适配器模式 (`BaseStorage`, `JSONStorage`, `SQLiteStorage`, `CloudflareD1Storage`)。
   - 前端 Web 页面基于 Tailwind CSS (暗黑/明亮双主题)，所有弹窗均已适配自研交互弹窗 (`showConfirmModal`) 与浮动 Toast (`showToast`)，请保持一致。
   - 保证基准货币统一核算原则（以 GBP 为基准核算股票估值、现金与盈亏）。

3. **提供改动摘要与验证指令**：
   - 简要说明改动的思路与关键逻辑。
   - 给出验证测试命令（如 `./run.sh web` 或 python 单元测试）。

---

## 🌳 项目目录结构 (Project File Tree)

```text
{file_tree}
```

---

## 📦 打包包含的文件清单 ({len(target_files)} 个文件)

{"\n".join(file_stats)}

---

## 📝 完整代码实现详情 (Source Code)

{"".join(file_contents)}

---
*(任务单结束，请基于以上上下文开始解答)*
"""
    return md


def run_packer(task: str = "", output_path: str = "ai_task_context.md", include_all: bool = False, files: Optional[List[str]] = None) -> None:
    """CLI runner to pack project context and notify user."""
    print("\n📦 正在扫描并打包项目代码库上下文...")
    md_content = build_pack_markdown(task_desc=task, included_files=files, include_all=include_all)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    file_size_kb = os.path.getsize(output_path) / 1024
    lines_count = md_content.count("\n")
    char_count = len(md_content)
    est_tokens = int(char_count / 3.5)

    print(f"✅ 上下文打包完成！已保存到: {output_path}")
    print(f"📊 统计: {lines_count:,} 行 | {char_count:,} 字符 | 约 {est_tokens:,} Tokens (约占网页端 Gemini 200万上下文的 {est_tokens / 20000:.1f}%)")

    copied = copy_to_clipboard(md_content)
    if copied:
        print("📋 【已自动复制到系统剪贴板！】")
        print("💡 请直接打开网页端 Gemini (https://gemini.google.com)，在输入框中按 Ctrl + V 粘贴发送！\n")
    else:
        print(f"💡 剪贴板工具未就绪，你可以直接打开 `{output_path}`，全选复制后粘贴到网页端 Gemini！\n")


if __name__ == "__main__":
    task_arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    run_packer(task=task_arg)
