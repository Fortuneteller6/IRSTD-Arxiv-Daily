"""CV-ARXIV-DAILY 入口脚本。

流程：
  1. 加载 config.yaml，解析启用的领域与搜索表达式
  2. 逐个领域抓取 arXiv 最新论文
  3. 按论文 ID 合并进统一 JSON 数据文件
  4. 根据发布开关渲染 README.md / docs/index.md

用法：
  python daily_arxiv.py [--config_path config.yaml]
"""

import argparse
import logging
from typing import Any, Dict

from arxiv_daily.codelink import backfill_code_links
from arxiv_daily.config import load_config
from arxiv_daily.fetcher import fetch_daily_papers
from arxiv_daily.renderer import render_markdown
from arxiv_daily.storage import load_data, merge_papers, save_data

logging.basicConfig(
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _write_markdown(path: str, content: str) -> None:
    """以 UTF-8 编码写入 Markdown 文件（避免 Windows 下乱码/崩溃）。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("已生成 %s", path)


def _render_outputs(config: Dict[str, Any], data: Dict[str, Any]) -> None:
    """按发布开关渲染 README.md / docs/index.md。"""
    user_name = config.get("user_name", "")
    repo_name = config.get("repo_name", "")
    show_badge = config.get("show_badge", True)

    if config.get("publish_readme", True):
        content = render_markdown(
            data,
            format="readme",
            show_badge=show_badge,
            user_name=user_name,
            repo_name=repo_name,
        )
        _write_markdown(config["md_readme_path"], content)

    if config.get("publish_gitpage", True):
        content = render_markdown(data, format="web")
        _write_markdown(config["md_gitpage_path"], content)


def run(config: Dict[str, Any]) -> None:
    """主流程：抓取 -> 合并 -> 渲染。"""
    # 1. 加载已有数据，并构建代码链接索引（避免对已知论文重复查询）
    data = load_data(config["data_path"])
    known_codes = None
    if config.get("enable_code_lookup", True):
        known_codes = {
            paper_id: paper["code"]
            for topic in config["kv"]
            for paper_id, paper in data.get(topic, {}).items()
            if paper.get("code")
        }

    # 2. 抓取每个启用领域的最新论文（新论文自动查找代码链接）
    new_papers_by_topic = {}
    for topic, query in config["kv"].items():
        max_results = config["domain_max_results"].get(
            topic, config.get("max_results", 10)
        )
        logger.info("开始抓取领域 %s（最多 %d 篇）", topic, max_results)
        new_papers_by_topic[topic] = fetch_daily_papers(
            topic, query, max_results, known_codes=known_codes
        )

    # 3. 合并进统一数据文件（论文 ID 去重，历史数据保留）
    for topic, papers in new_papers_by_topic.items():
        data = merge_papers(data, papers, topic)
    save_data(config["data_path"], data)
    logger.info("数据已写入 %s", config["data_path"])

    # 4. 渲染最终输出
    _render_outputs(config, data)

    logger.info("全部任务完成")


def run_backfill(config: Dict[str, Any]) -> None:
    """一次性回填：遍历已有数据，为缺失 code 的论文补齐链接并重新渲染。"""
    data = load_data(config["data_path"])
    data, updated = backfill_code_links(data)
    save_data(config["data_path"], data)
    _render_outputs(config, data)
    logger.info("代码链接回填完成，共补齐 %d 篇", updated)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="每日抓取 arXiv 论文并生成日报（README / GitPage）"
    )
    parser.add_argument(
        "--config_path",
        type=str,
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）",
    )
    parser.add_argument(
        "--backfill_code",
        action="store_true",
        help="遍历已有数据，为缺失代码链接的论文补齐链接（不抓取新论文）",
    )
    args = parser.parse_args()

    config = load_config(args.config_path)
    logger.info("配置加载完成，启用领域: %s", list(config["kv"].keys()))
    if args.backfill_code:
        run_backfill(config)
    else:
        run(config)


if __name__ == "__main__":
    main()
