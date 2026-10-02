#!/usr/bin/env python3
"""Obsidian / Markdown vault 体检脚本（PARA）。

用法：
    python3 scan_vault.py <vault路径>
    python3 scan_vault.py            # 默认当前目录

输出：
    1. 顶层目录结构（2 层）
    2. .md 总数与各 PARA 分区计数
    3. 缺 frontmatter 的笔记
    4. 有 frontmatter 但缺 type 字段的笔记
    5. 空 / 近乎空的笔记
    6. 99-Inbox 待处理数量
"""

import os
import re
import sys
from pathlib import Path

# 跳过的目录名
SKIP_DIRS = {".obsidian", ".git", ".trash", ".trash", "node_modules",
             ".merge-archive", ".dictionary", ".sessions"}
PARA_ROOTS = ["01-Projects", "02-Areas", "03-Resources", "04-Archives", "99-Inbox"]
# 正文去注释后少于该字符数视为近空
EMPTY_THRESHOLD = 20


def split_frontmatter(text: str):
    """返回 (frontmatter_str or None, body_str)。"""
    if text.startswith("---\n") or text.startswith("---\r\n"):
        # 找结束分隔符
        m = re.search(r"\r?\n---\r?\n", text[3:])
        if m:
            end = 3 + m.start()
            fm = text[3:end]
            body = text[3 + m.end():]
            return fm, body
    return None, text


def body_is_empty(body: str) -> bool:
    # 去除 HTML 注释
    b = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # 去除空白行与所有空白
    b = re.sub(r"\s+", "", b)
    # 去除未填写的任务/列表符号残留
    b = b.replace("-[]", "").replace("[[]]", "")
    return len(b) < EMPTY_THRESHOLD


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not root.is_dir():
        print(f"路径不是目录: {root}")
        sys.exit(1)

    md_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".md"):
                md_files.append(Path(dirpath) / fn)

    total = len(md_files)

    no_fm = []          # 缺 frontmatter
    no_type = []        # 缺 type
    empty = []          # 近空
    root_counts = {r: 0 for r in PARA_ROOTS}
    inbox_files = []

    for f in md_files:
        rel = f.relative_to(root)
        top = rel.parts[0] if len(rel.parts) > 1 else ""
        if top in root_counts:
            root_counts[top] += 1
        if top == "99-Inbox":
            inbox_files.append(rel)

        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

        fm, body = split_frontmatter(text)
        if fm is None:
            no_fm.append(rel)
            # 没 frontmatter 的也参与空判断
            if body_is_empty(text):
                empty.append(rel)
            continue
        if not re.search(r"^type\s*:", fm, flags=re.MULTILINE):
            no_type.append(rel)
        if body_is_empty(body):
            empty.append(rel)

    # ---- 输出 ----
    print("=" * 60)
    print(f"PARA Vault 体检：{root}")
    print("=" * 60)

    print("\n【顶层结构（2 层）】")
    for entry in sorted(root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            print(f"  {entry.name}/")
            try:
                children = sorted(entry.iterdir())
                shown = 0
                for c in children:
                    if c.name.startswith("."):
                        continue
                    suffix = "/" if c.is_dir() else ""
                    print(f"      {c.name}{suffix}")
                    shown += 1
                    if shown >= 12:
                        print("      ...")
                        break
            except PermissionError:
                pass
        else:
            print(f"  {entry.name}")

    print(f"\n【Markdown 总数】 {total}")
    print("\n【各 PARA 分区计数】")
    for r in PARA_ROOTS:
        print(f"  {r:<14} {root_counts[r]}")

    def report(title, items):
        print(f"\n【{title}】 {len(items)} 条")
        for it in items[:50]:
            print(f"  - {it}")
        if len(items) > 50:
            print(f"  ... 另有 {len(items) - 50} 条")

    report("缺 frontmatter", no_fm)
    report("frontmatter 缺 type 字段", no_type)
    report("空 / 近乎空笔记", empty)

    print(f"\n【99-Inbox 待处理】 {len(inbox_files)} 条")
    for it in inbox_files[:20]:
        print(f"  - {it.name}")

    # 健康度小结
    print("\n" + "=" * 60)
    issues = len(no_fm) + len(no_type) + len(empty) + len(inbox_files)
    if issues == 0:
        print("小结：库状态良好，无明显待整理项。")
    else:
        print(f"小结：共 {issues} 个待处理项（缺frontmatter {len(no_fm)} / "
              f"缺type {len(no_type)} / 近空 {len(empty)} / Inbox {len(inbox_files)}）。")
    print("=" * 60)


if __name__ == "__main__":
    main()
