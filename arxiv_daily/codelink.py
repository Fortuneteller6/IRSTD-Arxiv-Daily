"""代码链接查找与校验模块。

PapersWithCode API 已废弃，这里改用 GitHub 搜索 API 为论文匹配代码仓库，
按优先级尝试以下候选查询（命中即返回，按 star 排序取第一个）：
  1. arXiv ID（如 "2608.07015"）；
  2. 方法名/短标题（标题冒号前的部分，如 "LCPNet: ..." -> "LCPNet"）；
  3. 完整标题（截断到 80 字符）。

候选仓库在写入数据前会通过 verify_code_link 校验：读取仓库 README，
确认其中包含论文 arXiv ID，或与论文标题有足够多特征词重叠，
从而过滤掉同名但领域无关的仓库（如 irisnet 浏览器可视化工具）。

限流说明：
  - GitHub 搜索 API 未认证 10 次/分钟，认证后 30 次/分钟；
  - 本地无 token 时自动拉长请求间隔，CI 中通过 GITHUB_TOKEN 提速；
  - 命中 403/429 限流时按响应头 X-RateLimit-Reset 等待后继续。
"""

import logging
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_REPO_URL = "https://api.github.com/repos"
REQUEST_TIMEOUT = 15

# 请求间隔：未认证 6.5 秒/次（≈9.2 次/分钟，留有余量），认证后 2.2 秒/次
UNAUTHENTICATED_DELAY = 6.5
AUTHENTICATED_DELAY = 2.2

# 相关性校验使用的常见停用词
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "on", "in", "to", "with", "via",
    "using", "based", "from", "by", "at", "is", "are", "for", "towards",
    "toward", "over", "under", "into", "its", "it", "this", "that",
}


def _tokens(text: str) -> set:
    """把文本切分成小写词元集合（去停用词与单字母词）。"""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _headers() -> Dict[str, str]:
    """构造 GitHub API 请求头；有 GITHUB_TOKEN 时用于提升限流配额。"""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return {"Authorization": f"token {token}"}
    return {}


def _request_delay() -> float:
    """根据是否携带 token 返回请求间隔秒数。"""
    return AUTHENTICATED_DELAY if os.environ.get("GITHUB_TOKEN") else UNAUTHENTICATED_DELAY


def _search_repositories(query: str) -> Optional[str]:
    """执行一次 GitHub 仓库搜索，返回 star 最多的仓库地址；失败返回 None。"""
    params = {"q": query, "sort": "stars", "order": "desc"}
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(
                GITHUB_SEARCH_URL,
                params=params,
                headers=_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            break
        except requests.RequestException as exc:
            logger.warning("GitHub 搜索请求失败（第 %d 次）: %s", attempt + 1, exc)
            time.sleep(5)
    if resp is None:
        return None

    if resp.status_code in (403, 429):
        # 触发限流：按 X-RateLimit-Reset 等待（至少 30 秒），本次放弃
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
        wait = max(reset_ts - int(time.time()), 30)
        logger.warning("GitHub API 限流，等待 %d 秒后继续", wait)
        time.sleep(wait)
        return None

    if resp.status_code != 200:
        logger.warning("GitHub 搜索失败: HTTP %s", resp.status_code)
        return None

    items = resp.json().get("items") or []
    return items[0]["html_url"] if items else None


def _candidate_queries(arxiv_id: str, title: str) -> list:
    """生成候选搜索词（去重后保持顺序）。"""
    queries = [f'"{arxiv_id}"']

    # 方法名：标题冒号前的部分，如 "LCPNet: ..." -> "LCPNet"
    head = title.split(":", 1)[0].strip()
    if ":" in title and head and len(head) <= 40:
        queries.append(f'"{head}"')
    elif len(title.split()) <= 5 and title:
        # 无冒号且标题较短时，整个标题就是方法名
        queries.append(f'"{title}"')

    # 完整标题兜底（截断到 80 字符）
    short_title = title[:80].strip()
    if short_title:
        queries.append(f'"{short_title}"')

    return list(dict.fromkeys(queries))


def lookup_code_link(arxiv_id: str, title: str) -> Optional[str]:
    """查找论文对应的候选 GitHub 代码仓库；找不到返回 None。

    注意：返回的只是"候选"，写入前请调用 verify_code_link 做最终校验。
    """
    for query in _candidate_queries(arxiv_id, title):
        link = _search_repositories(query)
        if link:
            return link
        time.sleep(_request_delay())
    return None


def _fetch_readme(owner: str, repo: str, retries: int = 2) -> str:
    """获取仓库 README 原始文本；无 README 或请求失败返回空串。

    网络错误与限流都会等待后重试（最多 retries 次）。
    """
    url = f"{GITHUB_REPO_URL}/{owner}/{repo}/readme"
    resp = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                headers={**_headers(), "Accept": "application/vnd.github.raw"},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("README 请求失败 %s: %s", url, exc)
            time.sleep(5)
            continue
        if resp.status_code in (403, 429):
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_ts - int(time.time()), 30)
            logger.warning("README 请求限流，等待 %d 秒后重试", wait)
            time.sleep(wait)
            continue
        break
    return resp.text if resp is not None and resp.status_code == 200 else ""


def verify_code_link(arxiv_id: str, title: str, html_url: str) -> bool:
    """校验候选代码链接是否与论文相关。

    判据（满足其一即认为相关）：
      1. 仓库名/README 中包含论文 arXiv ID；
      2. 上述文本与论文标题至少共享 2 个词元，其中至少 2 个是
         长度 >= 5 的特征词（过滤 yolo/net 等通用短词）。

    仅读取一次 README；网络失败视为校验不通过。
    """
    parts = html_url.rstrip("/").split("/")
    if len(parts) < 5:
        return False
    owner, repo = parts[-2], parts[-1]

    readme = _fetch_readme(owner, repo)

    combined = f"{owner} {repo} {readme}"
    if arxiv_id in combined:
        return True

    overlap = _tokens(combined) & _tokens(title)
    long_overlap = [token for token in overlap if len(token) >= 5]
    return len(overlap) >= 2 and len(long_overlap) >= 2


def backfill_code_links(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """遍历所有领域中缺失 code 的论文，查找并校验后补齐链接。

    返回 (更新后的数据, 补齐的论文数量)。已有 code 的论文会被跳过，
    因此可以安全地重复执行。
    """
    updated = 0
    total = sum(
        1 for papers in data.values() for paper in papers.values()
        if not paper.get("code")
    )
    done = 0

    for topic, papers in data.items():
        for paper_id, paper in papers.items():
            if paper.get("code"):
                continue
            done += 1
            title = paper.get("title", "")
            logger.info(
                "查找代码链接 (%d/%d): %s %s",
                done, total, paper_id, title[:50],
            )
            candidate = lookup_code_link(paper_id, title)
            if candidate and verify_code_link(paper_id, title, candidate):
                paper["code"] = candidate
                updated += 1
                logger.info("找到并校验通过: %s", candidate)
            else:
                logger.info("未找到或校验未通过: %s", paper_id)

    return data, updated
