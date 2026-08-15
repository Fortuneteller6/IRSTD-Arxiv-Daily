"""JSON 数据 → Markdown 渲染模块。"""

import datetime
import re
from typing import Any, Dict, List, Tuple


def _pretty_math(text: str) -> str:
    """给 Markdown 中的行内公式 $...$ 两侧补空格，避免与前后文字粘连。"""
    match = re.search(r"\$.*\$", text)
    if match is None:
        return text

    start, end = match.span()
    before, after = text[:start], text[end:]
    # 前一个字符既不是空格也不是 * 时，在公式前补一个空格
    space_trail = "" if (not before or before[-1] in (" ", "*")) else " "
    # 后一个字符既不是空格也不是 * 时，在公式后补一个空格
    space_leading = "" if (not after or after[0] in (" ", "*")) else " "
    return (
        f"{before}{space_trail}${match.group()[1:-1].strip()}"
        f"${space_leading}{after}"
    )


def _sort_papers(papers: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """按发布日期倒序排列论文（同一天按论文 ID 倒序）。"""
    return sorted(
        papers.items(),
        key=lambda item: (item[1].get("publish_date", ""), item[0]),
        reverse=True,
    )


def _paper_row(paper_id: str, paper: Dict[str, Any]) -> str:
    """把单篇论文渲染成 Markdown 表格行。"""
    code = "null"
    if paper.get("code"):
        code = f"[link]({paper['code']})"
    return (
        f"|**{paper.get('publish_date', '')}**|**{paper.get('title', '')}**|"
        f"{paper.get('first_author', '')} et.al.|"
        f"[{paper_id}]({paper.get('url', '')})|{code}|\n"
    )


def _render_toc(data: Dict[str, Any]) -> List[str]:
    """渲染目录（Table of Contents）。"""
    lines = [
        "<details>",
        "  <summary>Table of Contents</summary>",
        "  <ol>",
    ]
    for topic, papers in data.items():
        if not papers:
            continue
        anchor = topic.replace(" ", "-").lower()
        lines.append(f"    <li><a href=#{anchor}>{topic}</a></li>")
    lines.append("  </ol>")
    lines.append("</details>")
    return lines


def _render_badges(user_name: str, repo_name: str) -> List[str]:
    """渲染 README 底部的 GitHub 徽章链接。"""
    shield = f"https://img.shields.io/github/{'{metric}'}/{user_name}/{repo_name}.svg?style=for-the-badge"
    lines = []
    for metric, label in [
        ("contributors", "contributors"),
        ("forks", "forks"),
        ("stars", "stars"),
        ("issues", "issues"),
    ]:
        lines.append(f"[{label}-shield]: {shield.format(metric=metric)}")
        lines.append(f"[{label}-url]: https://github.com/{user_name}/{repo_name}/{label}")
    return lines


def _render_tables(
    data: Dict[str, Any],
    to_web: bool,
    with_back_to_top: bool = False,
    today: str = "",
) -> List[str]:
    """渲染所有领域的论文表格（可选：每个领域后加"回到顶部"锚点）。"""
    lines = []
    for topic, papers in data.items():
        if not papers:
            continue
        lines.append(f"## {topic}")
        lines.append("")
        if to_web:
            lines.append("| Publish Date | Title | Authors | PDF | Code |")
            lines.append("|:---------|:-----------------------|:---------|:------|:------|")
        else:
            lines.append("|Publish Date|Title|Authors|PDF|Code|")
            lines.append("|---|---|---|---|---|")

        for paper_id, paper in _sort_papers(papers):
            lines.append(_pretty_math(_paper_row(paper_id, paper)).rstrip())
        lines.append("")

        if with_back_to_top:
            anchor = "#updated-on-" + today.replace(".", "")
            lines.append(f"<p align=right>(<a href={anchor.lower()}>back to top</a>)</p>")
            lines.append("")
    return lines


def render_markdown(
    data: Dict[str, Any],
    *,
    format: str = "readme",
    show_badge: bool = True,
    user_name: str = "",
    repo_name: str = "",
) -> str:
    """把领域数据渲染成 Markdown 文本。

    支持两种输出格式：
      - readme : 仓库主页 README（带目录、徽章、回到顶部）
      - web    : GitHub Pages 页面（带 Jekyll front matter，无目录/徽章）
    """
    today = str(datetime.date.today()).replace("-", ".")
    lines: List[str] = []

    if format == "web":
        lines += ["---", "layout: default", "---", ""]

    # 标题与更新时间
    lines.append(f"## Updated on {today}")
    lines.append("> Usage instructions: [here](./docs/README.md#usage)")
    lines.append("")

    if format == "readme":
        lines += _render_toc(data)
        lines.append("")
        lines += _render_tables(data, to_web=False, with_back_to_top=True, today=today)
        if show_badge:
            lines += _render_badges(user_name, repo_name)
            lines.append("")
    elif format == "web":
        lines += _render_tables(data, to_web=True)
    else:
        raise ValueError(f"未知的输出格式: {format}")

    return "\n".join(lines) + "\n"
