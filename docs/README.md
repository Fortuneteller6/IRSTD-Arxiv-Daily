# CV-ARXIV-DAILY（IRSTD 版）

基于原 [cv-arxiv-daily](https://github.com/Vincentqyw/cv-arxiv-daily) 方案重构的
arXiv 论文日报项目，默认聚焦 **IRSTD（红外小目标检测）** 领域，并支持通过
配置文件扩展任意研究领域。

## 项目结构

```text
cv-arxiv-daily-new/
├── daily_arxiv.py            # 入口脚本（抓取 -> 合并 -> 渲染）
├── config.yaml               # 领域/发布配置（重点）
├── requirements.txt          # Python 依赖
├── arxiv_daily/              # 核心模块
│   ├── config.py             # 配置解析 + 搜索表达式构建
│   ├── fetcher.py            # arXiv 论文抓取
│   ├── codelink.py           # GitHub 搜索匹配代码链接（含限流处理）
│   ├── storage.py            # JSON 数据读写与合并
│   └── renderer.py           # Markdown 渲染（README/GitPage）
├── tests/test_smoke.py       # 离线冒烟测试
├── docs/                     # GitHub Pages 站点（_config.yml + 生成页面）
└── .github/workflows/        # 每日自动更新工作流
```

## 快速开始

1. **Fork / 复制本仓库**，并修改 [config.yaml](../config.yaml) 中的
   `user_name` 和 `repo_name` 为自己的 GitHub 仓库信息。
2. 修改 [cv-arxiv-daily.yml](../.github/workflows/cv-arxiv-daily.yml) 顶部的
   `GITHUB_USER_NAME` 与 `GITHUB_USER_EMAIL`。
3. 在 GitHub 仓库 Settings → Actions → General 中，把 Workflow permissions
   改为 **Read and write permissions**。
4. 进入 Actions 页面，手动运行 **Run Arxiv Papers Daily** 工作流，约 1 分钟后
   生成的 README / 数据文件会自动提交回仓库。
5. （可选）启用 GitHub Pages：Settings → Pages → Source 选择
   `Deploy from a branch`，分支 `main`、目录 `/docs`，即可通过
   `https://<用户名>.github.io/<仓库名>/` 访问网页版日报。

## 本地运行

```bash
pip install -r requirements.txt
python daily_arxiv.py
```

运行后会生成/更新：

- `README.md`：仓库主页日报
- `docs/cv-arxiv-daily.json`：全部论文的结构化数据（历史积累）
- `docs/index.md`：GitHub Pages 页面

新抓取的论文会自动通过 GitHub 搜索 API 匹配代码仓库；要一次性补齐已有
历史论文的代码链接，执行：

```bash
python daily_arxiv.py --backfill_code
```

> 说明：GitHub 搜索 API 未认证限流 10 次/分钟，本地回填较多论文时耗时较长；
> 在 GitHub Actions 中会自动使用 `GITHUB_TOKEN`（30 次/分钟）。找不到代码
> 仓库的论文 Code 列保持 `null`，重新执行回填不会重复请求已有链接的论文。
> 候选链接会读取仓库 README 校验是否引用该论文（arXiv ID 或标题特征词），
> 以过滤同名无关仓库；校验逻辑可通过 `enable_code_lookup` 开关控制。

## 如何添加新领域（配置化扩展）

在 `config.yaml` 的 `domains` 下新增一个条目即可，无需改动任何代码：

```yaml
domains:
    "New Domain":
        enable: true
        max_results: 10
        filters:
            - "keyword1"
            - "keyword phrase 2"
```

说明：

- `enable: false` 时该领域停止抓取新论文，但历史数据保留在 JSON 中并继续展示；
- `max_results` 可覆盖全局默认值；
- `filters` 会自动以 `OR` 连接，含空格的多词短语自动加双引号按整体短语搜索；
- 想要彻底移除某个领域，直接删除该条目，或手动清理 JSON 中对应键。

## 测试

```bash
python tests/test_smoke.py
```

冒烟测试不依赖网络，覆盖配置解析、数据合并与两种 Markdown 格式渲染。

## 与原始项目的差异（优化点）

- 领域配置由 `keywords` 升级为 `domains`，支持 `enable` / 每领域 `max_results`；
- JSON 数据改为存储结构化字段（原来存的是 Markdown 字符串，不利于扩展）；
- 代码链接改用 GitHub 搜索 API（原 PapersWithCode API 已废弃），支持一键回填；
- 移除微信发布功能，只保留 README 与 GitHub Pages 两种输出；
- 所有文件读写统一 UTF-8，Windows 本地可直接运行；
- 代码拆分为配置/抓取/存储/渲染四个模块，并增加注释与冒烟测试。
