# daily

`daily` 是一个面向 Linux / macOS 的资讯 CLI。它把能力分成两层：

- 原子能力层：`trend`、`search`、`rss`
- 组合业务层：`summary`、`fetch`

这样后续新增来源、过滤器、正文增强器或新的业务 topic 时，都可以沿着同一套上层设计继续扩展。

## 设计概览

### 原子能力

- `daily trend`
  - 统一查看热榜源
  - 当前支持 `google`、`baidu`、`github`
- `daily search`
  - 统一做检索
  - 当前支持 `google`、`x`、`x-user`、`x-news`
- `daily rss`
  - 统一处理 RSSHub 与普通 RSS/Atom
  - 支持一次性抓取，也支持保存后批量拉取

### 组合业务

- `daily summary`
  - 输出默认 dashboard
- `daily fetch <topic ...>`
  - 获取一个或多个业务 topic
- `daily topics`
  - 查看业务 topic 定义

### 插件能力

- `filter`：语义分类与过滤

### Fetcher 能力

- `fetcher`：数据源抓取与正文抓取

当前默认过滤器是 `tfidf`，可切换到 `model`。正文抓取通过 Playwright 无头浏览器抓取完成。

## 内置业务 Topic

- `us-hot`
- `china-hot`
- `ai`
- `finance`
- `us-market`
- `github`

默认 `summary` 输出：

- `us-hot`
- `china-hot`
- `ai`
- `finance`
- `github`

## 安装

要求 Python `3.10+`。

基础安装：

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

全部能力：

```bash
python3 -m pip install '.[all]'
python3 -m playwright install chromium
daily model download
```

## 快速开始

```bash
daily trend
daily trend --source baidu --limit 20

daily search "OpenAI"
daily search "OpenAI" --source x
daily search elonmusk --source x-user

daily rss fetch https://36kr.com/feed
daily rss add rsshub://twitter/user/elonmusk --name Elon
daily rss pull

daily summary
daily fetch us-hot china-hot

daily x login
```

## 命令说明

### `daily trend`

统一查看热榜源。

```bash
daily trend
daily trend --source google
daily trend --source baidu --limit 20
daily trend --source all --format json
```

支持来源：

- `google`
- `baidu`
- `github`
- `all`

默认 `auto=all`。

### `daily search`

统一检索新闻、帖子与 X 用户公开发推。

```bash
daily search "人工智能"
daily search "OpenAI" --source x
daily search elonmusk --source x-user
daily search "AI" --source x-news
daily search "Federal Reserve" --fetch-body
```

支持来源：

- `google`
- `x`
- `x-user`
- `x-news`
- `all`

说明：

- `--source x` 使用 X recent search
- `--source x-user` 会把 query 当作 X 用户名
- `--source x-news` 使用 X news search
- `--source all` 会把 `google + x + x-news` 轮询混排并去重

### `daily rss`

统一处理 RSSHub 与普通 RSS/Atom。

一次性抓取：

```bash
daily rss fetch rsshub://twitter/user/elonmusk
daily rss fetch https://36kr.com/feed
```

保存与拉取：

```bash
daily rss add rsshub://twitter/user/elonmusk --name Elon
daily rss add https://36kr.com/feed --name 36kr
daily rss list
daily rss pull
daily rss remove twitter-user-elonmusk-xxxx
```

说明：

- `rsshub://twitter/user/elonmusk` 会被解析成 RSSHub 路由 `/twitter/user/elonmusk`
- 普通 RSS/Atom 直接使用公开 URL
- 默认实例是 `https://rsshub.app`
- 保存的订阅默认写到 `~/.config/daily/subscriptions.json`
- `subscriptions` 被收进 `rss` 命令下，因为它本质上是 feed 的保存与拉取，不是独立业务域

### `daily x`

只负责配置 X Bearer Token。

```bash
daily x login
daily x status
daily x logout
```

### `daily summary`

输出默认 dashboard。

```bash
daily summary
daily summary --filter-mode model
daily summary --fetch-body
```

### `daily fetch`

获取一个或多个业务 topic。

```bash
daily fetch us-hot
daily fetch china-hot ai finance
daily fetch us-market --source all --limit 8
daily fetch github --limit 10 --format json
```

### `daily topics`

查看业务 topic 注册表。

```bash
daily topics
daily topics --format json
```

## 过滤与正文增强

默认仅这两个 topic 会过滤 `soft`：

- `us-hot`
- `china-hot`

过滤模式：

- `tfidf`
  - 默认模式
  - `TF-IDF + LogisticRegression + 少量词表`
- `model`
  - `intfloat/multilingual-e5-small`
  - 需要先执行 `daily model download`

正文增强：

- 通过 `--fetch-body` 开启
- 只对最终保留结果抓正文
- `github` 默认不抓正文

## Python API

原子能力也可以直接从 Python 调用：

```python
from daily_cli.tools.search import collect_search
from daily_cli.tools.trend import collect_trends
from daily_cli.tools.rss import collect_rss
```

组合能力可以继续通过业务 topic 来复用。

## 项目结构

```text
daily_cli/
  __main__.py
  cli/
    main.py
  core/
    collector.py
    models.py
    specs.py
    topics.py
    subscriptions.py
    x_auth.py
  tools/
    search.py
    trend.py
    rss.py
  fetchers/
    common.py
    google.py
    baidu.py
    github.py
    x.py
    rss.py
    body.py
    crawlers/
      base.py
      playwright.py
    registry.py
  plugins/
    filters.py
    semantic.py
  common/
    config.py
    output.py
```

分层职责：

- `cli/`
  - 命令行参数与 help 面板
- `core/`
  - 领域模型、topic 注册表、订阅定义、统一编排
- `tools/`
  - 原子工具能力：`search` / `trend` / `rss`
- `fetchers/`
  - 每个来源一个独立抓取文件，正文抓取再拆到 `crawlers/` 子包
- `plugins/`
  - 目前只保留过滤插件
- `common/`
  - 通用配置与输出渲染

## 开发

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

查看帮助：

```bash
daily --help
daily trend --help
daily search --help
daily rss --help
```

更多设计说明：

- [Architecture](./docs/ARCHITECTURE.md)
- [News Pipeline](./docs/NEWS_PIPELINE.md)
