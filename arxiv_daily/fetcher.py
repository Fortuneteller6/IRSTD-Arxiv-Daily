"""arXiv 论文抓取模块。"""

import logging
from typing import Dict, List

import arxiv

from .codelink import lookup_code_link, verify_code_link

logger = logging.getLogger(__name__)

# arXiv 论文详情页地址模板
ARXIV_ABS_URL = "http://arxiv.org/abs/{}"


def _strip_version(paper_id: str) -> str:
    """去掉论文 ID 的版本号后缀，例如 2108.09112v1 -> 2108.09112。"""
    return paper_id.split("v")[0] if "v" in paper_id else paper_id


def fetch_daily_papers(
    topic: str,
    query: str,
    max_results: int,
    known_codes: Dict[str, str] = None,
) -> List[Dict]:
    """按搜索表达式抓取指定数量的最新论文。

    参数：
      topic        : 领域名（仅用于日志）
      query        : arXiv 搜索表达式（由 config.build_query 生成）
      max_results  : 返回的论文数量上限
      known_codes  : {论文ID: 代码链接}，已有链接的论文不再重复查询

    返回结构化论文字典列表，字段与 JSON 数据文件保持一致：
      id / publish_date / title / first_author / authors / url / code
    """
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    client = arxiv.Client()

    papers = []
    for result in client.results(search):
        paper_id = _strip_version(result.get_short_id())
        logger.info("抓取到论文 %s | %s", paper_id, result.title)

        # 已有链接直接用缓存；否则通过 GitHub 搜索补齐
        code = None
        if known_codes is not None:
            code = known_codes.get(paper_id)
            if not code:
                candidate = lookup_code_link(paper_id, result.title)
                if candidate and verify_code_link(paper_id, result.title, candidate):
                    code = candidate
                elif candidate:
                    logger.info("候选代码链接未通过校验，忽略: %s", candidate)

        papers.append({
            "id": paper_id,
            # 与原始项目保持一致：展示"最近更新日期"
            "publish_date": str(result.updated.date()),
            "title": result.title,
            "first_author": str(result.authors[0]) if result.authors else "",
            "authors": ", ".join(str(author) for author in result.authors),
            "url": ARXIV_ABS_URL.format(paper_id),
            "code": code,
        })

    logger.info("领域 %s 共抓取 %d 篇论文", topic, len(papers))
    return papers
