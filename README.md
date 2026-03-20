# daily

`daily` 是一个面向 Linux / macOS 的命令行资讯工具，用来快速查看每日热点、专题新闻信号、GitHub Trending，以及基于 Google / X / RSS 的跨源搜索结果。它优先使用公开、稳定、适合命令行接入的数据源，并把抓取、过滤、正文增强做成了可插拔的模块。

当前内置的 topics：

- `us-hot`：美国热门事件
- `china-hot`：中国热门事件
- `ai`：AI 发展
- `finance`：金融热门事件
- `us-market`：美股焦点
- `github`：GitHub Trending

额外能力：

- `search`：统一的跨源检索入口，支持 `google` / `x` / `x-user` / `x-news` / `all`
- `subscriptions`：RSSHub 与普通 RSS/Atom 订阅内容
- `x`：只负责配置 X Bearer Token，不再承担查询入口

## 特性

- 可安装的 Python CLI，入口命令为 `daily`
- topic、source、filter、enricher 分层注册，方便后续扩展
- 默认轻量模式使用 `TF-IDF + LogisticRegression + 词表` 做过滤
- 支持切换到 `intfloat/multilingual-e5-small` 的 `model` 模式
- 默认仅 `us-hot` / `china-hot` 过滤 `soft`
- `us-hot` 过滤后不足时，会自动回补 Google News Top Stories
- 支持 Playwright 无头模式抓正文
- 支持保存并拉取 RSSHub 与普通 RSS/Atom 订阅，例如 `rsshub://twitter/user/elonmusk`、`https://36kr.com/feed`
- 支持通过 X 官方 API v2 检索帖子、新闻故事，以及按用户名获取公开发推
- 支持文本和 JSON 两种输出

## 安装

要求 Python `3.10+`。

轻量安装，只使用默认的 `tfidf` 过滤模式：

```bash
python3 -m pip install .
```

如果你需要 `model` 过滤模式：

```bash
python3 -m pip install '.[model]'
daily model download
```

如果你需要正文抓取：

```bash
python3 -m pip install '.[body]'
python3 -m playwright install chromium
```

如果你想一次安装全部可选能力：

```bash
python3 -m pip install '.[all]'
python3 -m playwright install chromium
daily model download
```

## 快速开始

```bash
daily topics
daily summary
daily fetch us-hot china-hot
daily x login
daily search elonmusk --source x-user
daily subscriptions add rsshub://twitter/user/elonmusk --name Elon
daily subscriptions add https://36kr.com/feed --name 36kr
daily subscriptions fetch
daily fetch github --limit 10
daily search "人工智能" --google-locale cn
daily search "OpenAI" --source x
daily search "AI" --source x-news
```

## 命令

### `daily topics`

列出全部 topics、默认来源、默认数量和默认过滤策略。

```bash
daily topics
daily topics --format json
```

### `daily summary`

输出默认 dashboard：

- `us-hot`
- `china-hot`
- `ai`
- `finance`
- `github`

```bash
daily summary
daily summary --no-filter
daily summary --filter-mode model
```

### `daily x`

配置 X Bearer Token，供 `daily search --source x|x-user|x-news` 使用。

```bash
daily x login
daily x login <BEARER_TOKEN>
daily x status
daily x logout
```

说明：

- `daily x login` 不传 token 时，会在终端里安全输入
- 优先读取环境变量 `X_BEARER_TOKEN`
- 查询公开用户发推请使用 `daily search elonmusk --source x-user`
- 查询关键词帖子请使用 `daily search "OpenAI" --source x`
- 查询 X 新闻故事请使用 `daily search "AI" --source x-news`

### `daily fetch`

拉取一个或多个指定 topics。

```bash
daily fetch us-hot
daily fetch china-hot ai finance
daily fetch us-market --source all --limit 8
daily fetch github --limit 10 --format json
```

### `daily search`

统一的公共搜索入口。使用 Google News、X recent search、X user posts 或 X news search 按关键词或用户名查询。

```bash
daily search OpenAI
daily search "人工智能" --google-locale cn
daily search "OpenAI" --source x
daily search elonmusk --source x-user
daily search "AI" --source x-news
daily search "OpenAI" --source all
daily search "Federal Reserve" --fetch-body
```

说明：

- `search` 默认 `--source auto`，等价于 `google`
- `--source x` 使用 X recent search
- `--source x-user` 会把 query 当作 X 用户名，并返回该用户最近公开发推
- `--source x-news` 使用 X news search
- `--source all` 会把 `google + x + x-news` 混合去重后输出

如果你想在别的 Python 场景里复用同一条搜索链路，可以直接使用公开 API：

```python
from daily_cli.search import collect_search

section = collect_search(
    query="OpenAI",
    limit=5,
    timeout=10.0,
    source="x",
    google_locale="us",
)
```

### `daily subscriptions`

管理 RSSHub 与普通 RSS/Atom 订阅，支持保存、列出、删除、拉取和单次预览。

```bash
daily subscriptions add rsshub://twitter/user/elonmusk --name Elon
daily subscriptions add https://36kr.com/feed --name 36kr
daily subscriptions list
daily subscriptions fetch
daily subscriptions preview rsshub://twitter/user/elonmusk --instance https://your-rsshub.example
daily subscriptions preview https://36kr.com/feed --name 36kr
daily subscriptions remove twitter-user-elonmusk-xxxx
```

说明：

- `rsshub://twitter/user/elonmusk` 会被解析成 RSSHub 路由 `/twitter/user/elonmusk`
- `https://36kr.com/feed` 会被当作普通 RSS/Atom feed 直接抓取
- 默认实例是 `https://rsshub.app`
- 如果某个公共实例不支持对应 RSSHub 路由，可以显式传入 `--instance`
- 订阅配置默认保存在 `~/.config/daily/subscriptions.json`

### `daily model download`

下载 `model` 过滤模式所需的本地模型文件。

```bash
daily model download
daily model download --force
```

## 常用参数

```text
fetch/summary: --source auto|google|baidu|github|all
search: --source auto|google|x|x-user|x-news|all
--limit N
--timeout SECONDS
--format text|json
--filter-mode tfidf|model
--exclude-label macro|industry|tech|public|soft
--no-filter
--no-semantic
--semantic-model-dir PATH
--fetch-body
--body-timeout SECONDS
--body-max-chars N
```

补充说明：

- `auto`：使用 topic 推荐的默认来源
- `all`：聚合该 topic 支持的全部来源
- `search` 额外支持 `--source x`、`--source x-user`、`--source x-news`
- `search` 默认只检索，不自动分类；显式传入 `--exclude-label` 后才会启动过滤
- `github` 默认不做分类
- `github` 默认不抓正文
- `subscriptions fetch` / `subscriptions preview` 默认不自动过滤；显式传入 `--exclude-label` 后才会启动分类

## 默认行为

- 默认仅 `us-hot` / `china-hot` 过滤 `soft`
- `ai` / `finance` / `us-market` / `github` / `search` 默认只抓取，不自动分类
- 开启过滤后，会额外抓取更多候选，以保证过滤后尽量补足 `limit`
- `us-hot` 过滤后不足时，会按需用 Google News Top Stories 回补
- `tfidf` 是默认过滤模式，更适合开箱即用和开源分发
- `search --source x` / `x-user` / `x-news` 使用 X 官方 API v2，需要先运行 `daily x login` 或设置 `X_BEARER_TOKEN`
- RSSHub 订阅通过 `rsshub://` 自定义地址 + 实例地址解析成真实 feed URL
- 普通订阅直接使用公开 RSS/Atom URL，例如 `https://36kr.com/feed`

## Topic 概览

| Topic | 默认来源 | 默认数量 | 默认过滤 |
| --- | --- | --- | --- |
| `us-hot` | `google` | `5` | `soft` |
| `china-hot` | `baidu` | `5` | `soft` |
| `ai` | `google + baidu` | `5` | 无 |
| `finance` | `google + baidu` | `5` | 无 |
| `us-market` | `google + baidu` | `5` | 无 |
| `github` | `github` | `10` | 无 |

## 过滤模式

### `tfidf`

默认模式，内部使用：

- `TF-IDF`
- `LogisticRegression`
- 少量中英文词表与短语信号

这个模式适合：

- 开源项目默认发布
- 依赖更轻
- 无需提前下载大模型
- 启动更快

### `model`

使用 `intfloat/multilingual-e5-small` 做向量打标，适合需要更强语义能力的场景。

这个模式需要：

- 安装 `.[model]`
- 先执行 `daily model download`

## 正文抓取

传入 `--fetch-body` 后，`daily` 会在抓取、过滤、回补都完成之后，只对最终保留的链接抓正文。

当前正文抓取链路：

- 使用 Playwright Chromium 无头浏览器
- 优先等待 Google News 跳转到真实文章页
- 抽取 `article` / `main` 等正文容器
- 抽不到时回退到 `body.innerText`

当前边界：

- 某些站点会触发验证码、验证页或订阅墙
- `github` topic 默认不抓正文

## 项目结构

```text
daily_cli/
  __main__.py
  search.py      # 可复用的公共 search API
  cli.py         # CLI 参数与帮助面板
  core/
    config.py    # 通用配置目录与 JSON 配置读写
    models.py    # NewsItem / SectionResult 数据模型
    topics.py    # topic 注册表
    pipeline.py  # 抓取 / 过滤 / 回补 / 增强总管线
    subscriptions.py
    x_auth.py    # X Token 配置
  plugins/
    providers.py # source 插件注册表
    filters.py   # filter 插件注册表
    enrichers.py # body 等增强插件注册表
  runtime/
    sources.py   # 原始上游接口与解析器
    semantic.py  # tfidf/model 两套打标实现
    body_fetch.py
    rsshub.py
    x_api.py
  renderers/
    output.py    # text/json 输出
```

这套结构的目标是：

- CLI 只负责参数解析和输出
- source / filter / enricher 都能单独演进
- `collect_search` 可以被其他场景直接复用，不必绕 CLI
- 新增一个 topic 时，尽量只需要加注册表配置

## 开发

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

查看帮助：

```bash
daily --help
daily fetch --help
daily search --help
```

更详细的 topic、来源、排序、过滤和降级逻辑见：

- [docs/NEWS_PIPELINE.md](./docs/NEWS_PIPELINE.md)
