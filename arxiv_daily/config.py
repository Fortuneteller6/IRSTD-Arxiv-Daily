"""配置加载与 arXiv 搜索表达式构建。"""

from typing import Any, Dict, List

import yaml


def build_query(filters: List[str]) -> str:
    """把多个过滤词用 OR 连接成一条 arXiv 搜索表达式。

    含空格的多词短语会自动加双引号，保证作为整体短语搜索；
    单词直接保留。示例：
        ["Infrared Small Target Detection", "IRSTD"]
        -> '"Infrared Small Target Detection" OR IRSTD'
    """
    parts = []
    for keyword in filters:
        keyword = str(keyword).strip()
        if not keyword:
            continue
        if " " in keyword:
            parts.append(f'"{keyword}"')
        else:
            parts.append(keyword)
    return " OR ".join(parts)


def load_config(config_path: str) -> Dict[str, Any]:
    """读取 YAML 配置，解析出启用的领域信息。

    返回的字典在原始配置基础上额外增加两个字段：
      - kv                  : {领域名: 搜索表达式}
      - domain_max_results  : {领域名: 该领域每次抓取数量}
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 统一使用 domains 结构；兼容旧项目的 keywords 写法
    raw_domains = config.get("domains") or config.get("keywords") or {}
    global_max_results = config.get("max_results", 10)

    kv: Dict[str, str] = {}
    domain_max_results: Dict[str, int] = {}
    for topic, domain_cfg in raw_domains.items():
        if isinstance(domain_cfg, dict):
            # 新结构：{"enable": bool, "max_results": int, "filters": [...]}
            if not domain_cfg.get("enable", True):
                continue
            filters = domain_cfg.get("filters", [])
            max_results = domain_cfg.get("max_results", global_max_results)
        else:
            # 旧结构：keywords 直接是一个过滤词列表
            filters = domain_cfg
            max_results = global_max_results

        kv[topic] = build_query(filters)
        domain_max_results[topic] = max_results

    config["kv"] = kv
    config["domain_max_results"] = domain_max_results
    return config
