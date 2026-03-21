# wao / 哇哦

`wao`（中文名：`哇哦`）是一个面向 Linux / macOS 的资讯 CLI。它把能力分成两层：

- 原子能力层：`trend`、`search`、`rss`
- 组合业务层：`summary`、`fetch`

这样后续新增来源、过滤器、正文增强器或新的业务 topic 时，都可以沿着同一套上层设计继续扩展。

## 设计概览

### 原子能力

- `wao trend`
  - 统一查看热榜源
  - 当前支持 `google`、`baidu`、`github`
- `wao search`
  - 统一做检索
  - 当前支持 `google`、`x`、`x-user`、`x-news`
- `wao rss`
  - 统一处理 RSSHub 与普通 RSS/Atom
  - 支持一次性抓取，也支持保存后批量拉取

### 组合业务

- `wao summary`
  - 输出默认 dashboard
- `wao fetch <topic ...>`
  - 获取一个或多个业务 topic
- `wao topics`
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

一键安装脚本：

```bash
bash scripts/install.sh simple
bash scripts/install.sh full
```

- `simple`
  - 仅安装 `wao` 基础依赖
- `full`
  - 安装全部可选依赖
  - 安装 Playwright Chromium
  - 下载 `model` 过滤模式需要的模型

手动安装：

基础安装：

```bash
python3 -m pip install .
```

如果你需要 `model` 过滤模式：

```bash
python3 -m pip install '.[model]'
wao model download
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
wao model download
```

## 快速开始

```bash
wao trend
wao trend --source baidu --limit 20

wao search "OpenAI"
wao search "OpenAI" --source x
wao search elonmusk --source x-user

wao rss fetch https://36kr.com/feed
wao rss add rsshub://twitter/user/elonmusk --name Elon
wao rss pull

wao summary
wao fetch us-hot china-hot

wao x login
```

## 命令说明

### `wao trend`

统一查看热榜源。

```bash
wao trend
wao trend --source google
wao trend --source baidu --limit 20
wao trend --source all --format json
```

支持来源：

- `google`
- `baidu`
- `github`
- `all`

默认 `auto=all`。

### `wao search`

统一检索新闻、帖子与 X 用户公开发推。

```bash
wao search "人工智能"
wao search "OpenAI" --source x
wao search elonmusk --source x-user
wao search "AI" --source x-news
wao search "Federal Reserve" --fetch-body
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

### `wao rss`

统一处理 RSSHub 与普通 RSS/Atom。

一次性抓取：

```bash
wao rss fetch rsshub://twitter/user/elonmusk
wao rss fetch https://36kr.com/feed
```

保存与拉取：

```bash
wao rss add rsshub://twitter/user/elonmusk --name Elon
wao rss add https://36kr.com/feed --name 36kr
wao rss list
wao rss pull
wao rss remove twitter-user-elonmusk-xxxx
```

说明：

- `rsshub://twitter/user/elonmusk` 会被解析成 RSSHub 路由 `/twitter/user/elonmusk`
- 普通 RSS/Atom 直接使用公开 URL
- 默认实例是 `https://rsshub.app`
- 保存的订阅默认写到 `~/.config/wao/subscriptions.json`
- `subscriptions` 被收进 `rss` 命令下，因为它本质上是 feed 的保存与拉取，不是独立业务域

### `wao x`

只负责配置 X Bearer Token。

```bash
wao x login
wao x status
wao x logout
```

### `wao summary`

输出默认 dashboard。

```bash
wao summary
wao summary --filter-mode model
wao summary --fetch-body
```

### `wao fetch`

获取一个或多个业务 topic。

```bash
wao fetch us-hot
wao fetch china-hot ai finance
wao fetch us-market --source all --limit 8
wao fetch github --limit 10 --format json
```

### `wao topics`

查看业务 topic 注册表。

```bash
wao topics
wao topics --format json
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
  - 需要先执行 `wao model download`

正文增强：

- 通过 `--fetch-body` 开启
- 只对最终保留结果抓正文
- `github` 默认不抓正文

## Python API

原子能力也可以直接从 Python 调用：

```python
from wao.service.search import collect_search
from wao.service.trend import collect_trends
from wao.service.rss import collect_rss
```

组合能力可以继续通过业务 topic 来复用。

## 项目结构

```text
wao/
  __main__.py
  cli/
    cli.py
    args.py
    topics.py
    trend.py
    summary.py
    fetch.py
    search.py
    x.py
    rss.py
    model.py
  service/
    collector.py
    topics.py
    search.py
    trend.py
    rss.py
    subscriptions.py
  core/
    models.py
    specs.py
    config.py
    output.py
    x_auth.py
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
```

分层职责：

- `cli/`
  - `cli.py` 是总路由网关
  - `args.py` 放 CLI 公共参数与输出辅助
  - 每个一级命令一个独立文件
- `service/`
  - 原子查询与业务编排能力
  - 负责把 fetcher 和 plugin 组合成可直接调用的服务能力
- `core/`
  - 领域模型、配置、输出、规格和鉴权等核心基础能力
- `fetchers/`
  - 每个来源一个独立抓取文件，正文抓取再拆到 `crawlers/` 子包
- `plugins/`
  - 目前只保留过滤插件

## 开发

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

查看帮助：

```bash
wao --help
wao trend --help
wao search --help
wao rss --help
```

更多设计说明：

- [Architecture](./docs/ARCHITECTURE.md)
- [News Pipeline](./docs/NEWS_PIPELINE.md)
