# wao / 哇哦 Pipeline

本文档说明 `wao` 当前如何从原子能力拼出业务结果，以及数据源、排序、过滤和回补是怎么工作的。

## 1. 两层模型

### 原子能力层

- `wao trend`
- `wao search`
- `wao rss`

这些命令只负责“标准化获取信息”。

### 组合业务层

- `wao summary`
- `wao fetch`

这些命令只负责“把若干来源和默认规则组织成业务 topic”。

## 2. 当前原子能力

### 2.1 trend

统一热榜源：

- `google`
  - Google Trends RSS
- `baidu`
  - 百度热榜结构化数据
- `github`
  - GitHub Trending

`wao trend --source all` 会输出多个 section，不做强行混排。

### 2.2 search

统一检索源：

- `google`
  - Google News RSS search
- `x`
  - X recent search
- `x-user`
  - X user posts
- `x-news`
  - X news search

`wao search --source all` 会把：

- `google`
- `x`
- `x-news`

按轮询方式混排并去重。`x-user` 不参与 `all`，因为它是用户名语义，不是关键词检索语义。

### 2.3 rss

统一 feed 能力：

- RSSHub route
- 普通 RSS / Atom URL

它既支持一次性抓取，也支持保存后批量拉取：

- `wao rss fetch ...`
- `wao rss add ...`
- `wao rss pull`

## 3. 当前业务 Topic

| Topic | 默认来源 | 默认数量 | 默认过滤 |
| --- | --- | --- | --- |
| `us-hot` | `google` | `5` | `soft` |
| `china-hot` | `baidu` | `5` | `soft` |
| `ai` | `google + baidu` | `5` | 无 |
| `finance` | `google + baidu` | `5` | 无 |
| `us-market` | `google + baidu` | `5` | 无 |
| `github` | `github` | `10` | 无 |

默认 `summary` 包含：

- `us-hot`
- `china-hot`
- `ai`
- `finance`
- `github`

## 4. 数据源明细

### 4.1 Google Trends

接口：

```text
https://trends.google.com/trending/rss?geo=US
```

用于：

- `wao trend --source google`
- `us-hot`

### 4.2 Google News

接口：

```text
https://news.google.com/rss/search?q=...&hl=...&gl=...&ceid=...
https://news.google.com/rss?hl=...&gl=...&ceid=...
```

用于：

- `wao search --source google`
- `ai`
- `finance`
- `us-market`
- `us-hot` 回补

### 4.3 百度热榜

页面：

```text
https://top.baidu.com/board?tab=realtime
```

用于：

- `wao trend --source baidu`
- `china-hot`
- `ai` / `finance` / `us-market` 的关键词过滤补充

### 4.4 GitHub Trending

页面：

```text
https://github.com/trending
```

用于：

- `wao trend --source github`
- `github`

### 4.5 X API

接口：

```text
GET /2/tweets/search/recent
GET /2/users/by/username/:username
GET /2/users/:id/tweets
GET /2/news/search
```

用于：

- `wao search --source x`
- `wao search --source x-user`
- `wao search --source x-news`

### 4.6 RSSHub / RSS / Atom

用于：

- `wao rss`

当前支持：

- `rsshub://twitter/user/elonmusk`
- `https://36kr.com/feed`

## 5. 排序与去重

### 单来源

单来源保留上游顺序，再做标题去重。

### 多来源

多来源使用轮询合并：

1. 先取每个来源第 1 条
2. 再取每个来源第 2 条
3. 依次继续

这样能避免一个来源完全淹没其他来源。

### 去重

去重基于标准化标题：

- 折叠空白
- 去首尾空格
- 小写比较

## 6. 过滤链路

### 默认启用范围

默认只有：

- `us-hot`
- `china-hot`

会自动过滤 `soft`。

这些内容默认只抓取，不自动过滤：

- `wao trend`
- `wao search`
- `wao rss`
- `ai`
- `finance`
- `us-market`
- `github`

只有显式传入 `--exclude-label` 时，才会启动过滤。

### 候选放大

只要启用过滤，就不是只抓最终 `limit`，而是先抓更多候选：

```text
max(limit * 3, limit + 8)
```

### 回补

当前只有 `us-hot` 配置了回补：

- 主来源：Google Trends
- 回补来源：Google News Top Stories

当过滤后数量不足时，会按需拉 Google News 补量。

## 7. 插件层

### filter

负责“怎么打标签、怎么过滤”。

当前内置：

- `tfidf`
- `model`

## 8. Fetcher 层

Fetcher 负责“从哪取、怎么取正文”。

当前按来源拆分：

- `google`
- `baidu`
- `github`
- `x`
- `rss`
- `body`

其中浏览器型正文抓取进一步拆到了：

- `fetchers/crawlers/base.py`
- `fetchers/crawlers/playwright.py`

## 9. 正文抓取

传入 `--fetch-body` 后，正文抓取只会发生在最终保留结果上。

当前策略：

- 通过 `fetchers/body.py` 统一编排
- 具体浏览器实现由 `fetchers/crawlers/playwright.py` 提供
- 使用 Playwright Chromium 无头模式
- 优先处理 Google News 跳转
- 优先抽 `article` / `main`
- 抽不到再回退 `body.innerText`

当前限制：

- 某些站点会触发验证页
- `github` 默认不抓正文

## 10. 代码对应关系

- 原子公共入口：
  - `wao/service/search.py`
  - `wao/service/trend.py`
  - `wao/service/rss.py`
- collector 门面：
  - `wao/service/collector.py`
- 业务 topic 定义：
  - `wao/service/topics.py`
- 核心基础能力：
  - `wao/core/`
- 过滤插件：
  - `wao/plugins/`
- 数据抓取与正文抓取：
  - `wao/fetchers/`
