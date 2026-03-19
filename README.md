# daily

`daily` 是一个面向 Linux / macOS 的命令行资讯工具，用来快速查看每日热点、专题新闻信号和 GitHub Trending。它优先使用公开、稳定、适合命令行接入的数据源，并把抓取、过滤、正文增强做成了可插拔的模块。

当前内置的 topics：

- `us-hot`：美国热门事件
- `china-hot`：中国热门事件
- `ai`：AI 发展
- `finance`：金融热门事件
- `us-market`：美股焦点
- `github`：GitHub Trending
- `search`：自定义 Google News 查询

## 特性

- 可安装的 Python CLI，入口命令为 `daily`
- topic、source、filter、enricher 分层注册，方便后续扩展
- 默认轻量模式使用 `TF-IDF + LogisticRegression + 词表` 做过滤
- 支持切换到 `intfloat/multilingual-e5-small` 的 `model` 模式
- 默认仅 `us-hot` / `china-hot` 过滤 `soft`
- `us-hot` 过滤后不足时，会自动回补 Google News Top Stories
- 支持 Playwright 无头模式抓正文
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
daily fetch github --limit 10
daily search "人工智能" --google-locale cn
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

### `daily fetch`

拉取一个或多个指定 topics。

```bash
daily fetch us-hot
daily fetch china-hot ai finance
daily fetch us-market --source all --limit 8
daily fetch github --limit 10 --format json
```

### `daily search`

使用 Google News RSS 按关键词查询。

```bash
daily search OpenAI
daily search "人工智能" --google-locale cn
daily search "Federal Reserve" --fetch-body
```

### `daily model download`

下载 `model` 过滤模式所需的本地模型文件。

```bash
daily model download
daily model download --force
```

## 常用参数

```text
--source auto|google|baidu|github|all
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
- `search` 默认只检索，不自动分类；显式传入 `--exclude-label` 后才会启动过滤
- `github` 默认不做分类，也不抓正文

## 默认行为

- 默认仅 `us-hot` / `china-hot` 过滤 `soft`
- `ai` / `finance` / `us-market` / `github` / `search` 默认只抓取，不自动分类
- 开启过滤后，会额外抓取更多候选，以保证过滤后尽量补足 `limit`
- `us-hot` 过滤后不足时，会按需用 Google News Top Stories 回补
- `tfidf` 是默认过滤模式，更适合开箱即用和开源分发

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
  cli.py         # CLI 参数与帮助面板
  core/
    models.py    # NewsItem / SectionResult 数据模型
    topics.py    # topic 注册表
    pipeline.py  # 抓取 / 过滤 / 回补 / 增强总管线
  plugins/
    providers.py # source 插件注册表
    filters.py   # filter 插件注册表
    enrichers.py # body 等增强插件注册表
  runtime/
    sources.py   # 原始上游接口与解析器
    semantic.py  # tfidf/model 两套打标实现
    body_fetch.py
  renderers/
    output.py    # text/json 输出
```

这套结构的目标是：

- CLI 只负责参数解析和输出
- source / filter / enricher 都能单独演进
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
