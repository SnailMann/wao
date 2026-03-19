# daily 资讯聚合与过滤设计

本文档说明 `daily` 当前版本如何组织 topics、使用哪些公开来源、如何排序与去重、什么时候启用过滤、以及插件式结构是如何工作的。

## 1. 设计目标

`daily` 不是通用新闻门户，也不是全文搜索引擎。它更像一个面向命令行的每日信号面板，强调：

- 公开可访问的数据源
- 尽量稳定的抓取方式
- 快速查看而不是重型部署
- 默认轻量、可选增强
- 易扩展的 topic / provider / filter / enricher 架构

## 2. 代码结构

当前项目按职责拆成 5 层：

### 2.1 `core/topics.py`

负责定义 topic 注册表。每个 topic 会描述：

- key
- label
- description
- source plans
- default sources
- default limit
- default excluded labels
- optional refill plan

### 2.2 `plugins/providers.py`

负责 source 插件注册表。当前内置：

- `google`
- `baidu`
- `github`

每个 source 再按 mode 派发到具体抓取实现，例如：

- `google:trends_us`
- `google:news_search`
- `google:news_top`
- `baidu:hotboard`
- `baidu:keyword_hotboard`
- `github:trending`

### 2.3 `plugins/filters.py`

负责过滤模式注册表。当前内置：

- `tfidf`
- `model`

### 2.4 `plugins/enrichers.py`

负责结果增强插件。当前内置：

- `body`

### 2.5 `core/pipeline.py`

负责把 topic、provider、filter、enricher 串起来，统一处理：

- 抓取
- 合并
- 去重
- 分类
- 过滤
- 回补
- 正文增强

## 3. Topic 一览

| Topic | 中文名称 | 默认来源 | 默认数量 | 默认过滤 |
| --- | --- | --- | --- | --- |
| `us-hot` | 美国热门事件 | `google` | `5` | `soft` |
| `china-hot` | 中国热门事件 | `baidu` | `5` | `soft` |
| `ai` | AI 发展 | `google + baidu` | `5` | 无 |
| `finance` | 金融热门事件 | `google + baidu` | `5` | 无 |
| `us-market` | 美股焦点 | `google + baidu` | `5` | 无 |
| `github` | GitHub Trending | `github` | `10` | 无 |
| `search` | 自定义查询 | `google` | 用户指定 | 无 |

默认摘要 `summary` 会输出：

- `us-hot`
- `china-hot`
- `ai`
- `finance`
- `github`

## 4. 数据源

### 4.1 Google

#### `trends_us`

接口：

```text
https://trends.google.com/trending/rss?geo=US
```

用途：

- `us-hot`

特点：

- 更适合表示“今天美国在搜什么”
- 标题通常更短、更像趋势词而不是完整新闻标题

#### `news_search`

接口：

```text
https://news.google.com/rss/search?q=...&hl=...&gl=...&ceid=...
```

用途：

- `ai`
- `finance`
- `us-market`
- `search`

#### `news_top`

接口：

```text
https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en
```

用途：

- 仅用作 `us-hot` 的回补源

### 4.2 Baidu

#### `hotboard`

页面：

```text
https://top.baidu.com/board?tab=realtime
```

用途：

- `china-hot`

实现：

- 不依赖 DOM class
- 直接解析页面里的结构化数据块

#### `keyword_hotboard`

用途：

- `ai`
- `finance`
- `us-market`

实现：

1. 先抓百度热榜
2. 再基于关键词做二次过滤

### 4.3 GitHub

#### `trending`

页面：

```text
https://github.com/trending
```

用途：

- `github`

输出字段：

- 仓库名
- 描述
- 语言
- Stars
- Forks
- 今日新增 Stars

## 5. Topic 是怎么定义的

### 5.1 来源定义型 topic

这类 topic 的边界主要由来源决定：

- `us-hot`
- `china-hot`
- `github`

其中：

- `us-hot` 的主来源是 Google Trends US
- `china-hot` 的主来源是百度热榜
- `github` 的主来源是 GitHub Trending

### 5.2 查询定义型 topic

这类 topic 的边界主要由查询词或关键词决定：

- `ai`
- `finance`
- `us-market`
- `search`

例如：

- `ai` 通过固定 Google News 查询词定义边界
- `finance` 通过固定金融查询词定义边界
- `us-market` 通过美股查询词定义边界
- `search` 直接使用用户输入的查询词

## 6. 多来源排序与去重

### 6.1 单来源

单来源 topic 会保留上游原始顺序，再做标题去重。

### 6.2 多来源

当一个 topic 同时使用多个来源时，`daily` 会按“轮询合并”方式混排：

1. 先取每个来源的第 1 条
2. 再取每个来源的第 2 条
3. 以此类推

这样做的目的：

- 避免某一个来源完全淹没其他来源
- 让最终结果更像“混合信号流”

### 6.3 去重

去重规则基于标准化标题：

- 折叠空白
- 去掉首尾空格
- 转小写比较

如果标准化标题重复，则只保留第一次出现的条目。

## 7. 过滤链路

### 7.1 默认是否启动过滤

默认仅这两个 topic 会启动过滤：

- `us-hot`
- `china-hot`

默认过滤标签：

- `soft`

这些 topic 默认不自动分类：

- `ai`
- `finance`
- `us-market`
- `github`
- `search`

它们只有在显式传入 `--exclude-label` 时，才会进入分类和过滤链路。

### 7.2 为什么不是所有 topic 都默认过滤

因为分类本身有成本：

- 要抓更多候选
- 要跑打标
- 还可能误伤高价值内容

所以当前策略是：

- 杂讯最多的 `us-hot` / `china-hot` 默认过滤
- 其他更专题化的 topic 默认不动

### 7.3 候选放大

一旦启用过滤，抓取阶段不会只抓最终 `limit`，而是先抓更多候选：

```text
max(limit * 3, limit + 8)
```

这样做是为了在过滤掉一部分内容后，仍然有机会补足结果数量。

## 8. 过滤模式

### 8.1 `tfidf`

这是默认模式，也是开源分发时的推荐模式。

内部由三部分组成：

- `TF-IDF`
- `LogisticRegression`
- 少量中英文词表 / 短语信号

训练语料来源：

- 由 `model` 模式生成的一批伪标签样本
- 补充的少量人工构造样本

适合：

- 默认安装
- 启动更快
- 无需提前下载大模型

### 8.2 `model`

使用：

```text
intfloat/multilingual-e5-small
```

适合：

- 需要更强语义能力
- 愿意接受更高的模型下载和运行成本

## 9. 标签体系

当前标签保持少量且稳定：

- `macro`
- `industry`
- `tech`
- `public`
- `soft`

其中 `soft` 表示：

- 猎奇
- 八卦
- 情绪化个体故事
- 流量型社会新闻
- 缺少明显公共价值或认知增量的内容

## 10. 回补逻辑

当前只有 `us-hot` 配置了回补。

逻辑如下：

1. 先抓 Google Trends US
2. 如果默认 `soft` 过滤后不足 `limit`
3. 再抓 Google News Top Stories
4. 对回补条目继续做同样的分类和过滤
5. 只追加未重复且未被过滤掉的结果

这样可以缓解 Google Trends 标题过短、娱乐噪声偏多的问题。

## 11. 正文抓取

启用 `--fetch-body` 后，正文抓取只会发生在：

- 抓取完成后
- 过滤完成后
- 回补完成后
- 最终保留的结果上

正文抓取当前使用 Playwright Chromium：

- 支持等待 Google News 跳转到真实文章页
- 优先抽取 `article` / `main`
- 失败时回退到 `body.innerText`

已知边界：

- 站点验证码
- 访问验证页
- 订阅墙
- 某些新闻站的客户端渲染页面

## 12. 失败与降级

当某个来源失败时：

- 不会让整个命令失败
- 会把失败原因写进该 section 的 warnings
- 如果其他来源仍然成功，结果照常返回

例如：

- 某个 Google RSS 请求超时
- Baidu 热榜当前不可用
- GitHub Trending 当天只解析到少量条目
- 正文抓取命中验证页

## 13. 为什么采用插件式结构

因为这个项目的扩展点非常明确：

- 新增 topic
- 新增 source
- 新增 filter
- 新增 enricher

当前结构让这些变化更容易做到局部修改：

- 加一个 topic，优先改 `core/topics.py`
- 加一个来源模式，优先改 `plugins/providers.py`
- 加一个过滤后端，优先改 `plugins/filters.py`
- 加一个增强能力，优先改 `plugins/enrichers.py`

这样可以避免把所有逻辑继续堆回一个巨大的 `service.py` 里。
