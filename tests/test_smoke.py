"""离线冒烟测试：不依赖网络，验证配置解析、数据合并与 Markdown 渲染。

运行方式：python tests/test_smoke.py
"""

import os
import sys
import tempfile

# 保证可以直接从项目根目录下运行
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from arxiv_daily.config import build_query, load_config  # noqa: E402
from arxiv_daily.renderer import render_markdown  # noqa: E402
from arxiv_daily.storage import load_data, merge_papers, save_data  # noqa: E402


def test_build_query():
    """多词短语加引号，单词保留，OR 连接。"""
    query = build_query(["Infrared Small Target Detection", "IRSTD"])
    assert query == '"Infrared Small Target Detection" OR IRSTD'

    query = build_query([])
    assert query == ""


def test_config():
    """配置应只启用 IRSTD，且每领域抓取数量正确。"""
    config = load_config(os.path.join(PROJECT_ROOT, "config.yaml"))
    assert list(config["kv"].keys()) == ["IRSTD"]
    assert "Infrared Small Target Detection" in config["kv"]["IRSTD"]
    assert config["domain_max_results"]["IRSTD"] == 10


def test_merge_papers():
    """论文按 ID 合并，重复抓取不会产生重复条目。"""
    paper = {
        "id": "2608.07015",
        "publish_date": "2026-08-07",
        "title": "Demo Paper",
        "first_author": "Alice",
        "authors": "Alice, Bob",
        "url": "http://arxiv.org/abs/2608.07015",
        "code": None,
    }
    data = merge_papers({}, [paper], "IRSTD")
    assert data["IRSTD"]["2608.07015"]["title"] == "Demo Paper"

    # 同一 ID 重复合并只保留一篇
    data = merge_papers(data, [paper], "IRSTD")
    assert len(data["IRSTD"]) == 1


def test_render_markdown():
    """两种输出格式都能正确渲染。"""
    data = {
        "IRSTD": {
            "2608.07015": {
                "id": "2608.07015",
                "publish_date": "2026-08-07",
                "title": "Demo Paper",
                "first_author": "Alice",
                "authors": "Alice, Bob",
                "url": "http://arxiv.org/abs/2608.07015",
                "code": None,
            }
        }
    }

    readme = render_markdown(data, format="readme", show_badge=False)
    assert "## IRSTD" in readme
    assert "2608.07015" in readme
    assert "null" in readme

    web = render_markdown(data, format="web")
    assert web.startswith("---\nlayout: default\n---")


def test_render_code_link():
    """code 字段有值时渲染成 [link](url)，而不是 null。"""
    data = {
        "IRSTD": {
            "2608.07015": {
                "id": "2608.07015",
                "publish_date": "2026-08-07",
                "title": "Demo Paper",
                "first_author": "Alice",
                "authors": "Alice, Bob",
                "url": "http://arxiv.org/abs/2608.07015",
                "code": "https://github.com/foo/bar",
            }
        }
    }
    readme = render_markdown(data, format="readme", show_badge=False)
    assert "[link](https://github.com/foo/bar)" in readme
    assert "|null|" not in readme


def test_lookup_code_link():
    """GitHub 搜索结果能正确解析为仓库地址。"""
    from unittest import mock

    from arxiv_daily import codelink

    fake_resp = mock.Mock()
    fake_resp.status_code = 200
    fake_resp.headers = {}
    fake_resp.json.return_value = {
        "items": [{"html_url": "https://github.com/foo/bar"}]
    }

    with mock.patch.object(codelink.requests, "get", return_value=fake_resp), \
            mock.patch.object(codelink.time, "sleep"):
        link = codelink.lookup_code_link("2608.07015", "Demo Title")
    assert link == "https://github.com/foo/bar"


def test_verify_code_link():
    """verify_code_link 通过 README 内容校验真伪匹配。"""
    from unittest import mock

    from arxiv_daily import codelink

    def fake_get(url, *args, **kwargs):
        resp = mock.Mock()
        resp.status_code = 200
        # README 中引用了论文 arXiv ID
        resp.text = (
            "Official implementation of HyTBE. "
            "Paper: arXiv:2608.05771"
        )
        return resp

    with mock.patch.object(codelink.requests, "get", side_effect=fake_get):
        assert codelink.verify_code_link(
            "2608.05771",
            "HyTBE: Hyperbolic Target-Background Expert Model for Cross-Domain Infrared Small Target Detection",
            "https://github.com/PepperCS/HyTBE",
        )

    def fake_get_bad(url, *args, **kwargs):
        resp = mock.Mock()
        resp.status_code = 200
        # 同名仓库：内容是完全无关的浏览器可视化工具
        resp.text = "IrisNet: browser based neural network visualization tool."
        return resp

    with mock.patch.object(codelink.requests, "get", side_effect=fake_get_bad):
        assert not codelink.verify_code_link(
            "2511.20319",
            "IrisNet: Infrared Image Status Awareness Meta Decoder for Infrared Small Targets Detection",
            "https://github.com/irisnet/irisnet",
        )


def test_storage_roundtrip():
    """JSON 读写往返一致，且缺失文件返回空字典。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "data.json")
        save_data(path, {"IRSTD": {}})
        assert load_data(path) == {"IRSTD": {}}
        assert load_data(os.path.join(tmp_dir, "missing.json")) == {}


if __name__ == "__main__":
    for fn in (
        test_build_query,
        test_config,
        test_merge_papers,
        test_render_markdown,
        test_render_code_link,
        test_lookup_code_link,
        test_verify_code_link,
        test_storage_roundtrip,
    ):
        fn()
        print(f"PASS {fn.__name__}")
    print("所有离线冒烟测试通过。")
