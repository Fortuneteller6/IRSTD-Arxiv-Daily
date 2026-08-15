"""JSON 数据文件的读写与合并。"""

import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def load_data(path: str) -> Dict[str, Any]:
    """读取 JSON 数据文件；文件不存在或为空时返回空字典。"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return json.loads(content) if content else {}


def save_data(path: str, data: Dict[str, Any]) -> None:
    """把数据写回 JSON 文件。

    统一使用 UTF-8 编码，避免 Windows 环境下中文等字符乱码；
    ensure_ascii=False 保证非 ASCII 字符以原文存储，便于阅读。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_papers(
    existing: Dict[str, Any],
    new_papers: List[Dict],
    topic: str,
) -> Dict[str, Any]:
    """把新抓取的论文按 ID 合并进已有数据。

    以论文 ID 为主键，重复抓取同一篇论文会自动覆盖更新（幂等）。
    """
    result = dict(existing)
    topic_data = dict(result.get(topic, {}))

    for paper in new_papers:
        topic_data[paper["id"]] = paper

    result[topic] = topic_data
    logger.info("领域 %s 合并完成，累计 %d 篇", topic, len(topic_data))
    return result
