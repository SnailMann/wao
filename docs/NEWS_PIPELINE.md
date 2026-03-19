# daily-cli 资讯分类与聚合设计说明

本文档说明 `daily-cli` 当前版本如何定义资讯类别、如何判断类别、使用了哪些数据源、如何做多来源排序、去重与降级，以及当前实现的边界。

当前版本还包含一个默认开启的语义过滤层：

- 默认使用 `tfidf + LogisticRegression + 少量词表`
- 也支持 `intfloat/multilingual-e5-small`
- 默认仅 `us-hot` / `china-hot` 触发 `soft` 过滤
- 未配置过滤的 preset 默认不会启动分类
- 可通过 CLI 参数关闭过滤或切换后端
- 只有启用过滤的分组才会额外放大抓取条数并进入分类链路

## 1. 设计目标

`daily-cli` 的目标不是做“通用新闻门户”，而是提供一个偏实用的命令行聚合工具，让用户可以快速查看：

- 美国热门事件
- 中国热门事件
- AI发展
- 金融热门事件
- GitHub Trending
- 美股焦点
- 自定义关键词结果

它强调：

- 可安装、可本地运行
- 尽量依赖稳定且公开可访问的接口
- 面向命令行的快速查看体验
- 尽量减少重依赖和复杂部署

## 2. 预设类别总览

### 2.1 默认摘要

`summary` 命令会固定输出 5 个分组：

- `us-hot`
- `china-hot`
- `ai`
- `finance`
- `github`

### 2.2 全部预设

| 预设 | 中文名称 | 默认来源 | 说明 |
| --- | --- | --- | --- |
| `us-hot` | 美国热门事件 | `google` | 依赖 Google Trends US 日趋势，过滤后不足时按需回补 Google News Top Stories |
| `china-hot` | 中国热门事件 | `baidu` | 依赖百度热榜实时榜 |
| `ai` | AI发展 | `google + baidu` | Google News AI 查询 + 百度热榜关键词过滤 |
| `finance` | 金融热门事件 | `google + baidu` | Google News 金融查询 + 百度热榜关键词过滤 |
| `github` | GitHub Trending | `github` | GitHub Trending 热门仓库列表 |
| `us-market` | 美股焦点 | `google + baidu` | Google News 美股查询 + 百度热榜关键词过滤 |
| `search` | 自定义查询 | `google` | 按用户输入关键词通过 Google News 查询 |

## 3. 数据源清单

### 3.1 Google 来源

#### A. Google Trends RSS

用途：

- `us-hot`

当前使用的接口：

```text
https://trends.google.com/trending/rss?geo=US
```

解析字段：

- `title`
- `ht:approx_traffic`
- `pubDate`
- `ht:news_item_title`
- `ht:news_item_source`
- `ht:news_item_url`

说明：

- `us-hot` 的主来源是 Google Trends RSS。
- 当默认 `soft` 过滤开启且剩余条目不足时，会额外拉取 Google News Top Stories 进行回补。
- Google Trends 原始条目仍优先展示，回补条目只在数量不足时追加到后面。

#### B. Google News RSS Search

用途：

- `ai`
- `finance`
- `us-market`
- `search`

当前使用的接口：

```text
https://news.google.com/rss/search?q=...&hl=...&gl=...&ceid=...
```

当前代码内使用的主要查询词：

- `ai`
  - `AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Gemini OR Nvidia`
- `finance`
  - `"stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones" OR "Federal Reserve" OR earnings OR inflation`
- `us-market`
  - `"US stocks" OR "stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones"`

`search` 命令直接把用户的原始查询词作为 `q` 参数传入。

### 3.2 Baidu 来源

#### A. 百度热榜实时榜

用途：

- `china-hot`
- `ai` / `finance` / `us-market` / `search` 的热榜补充来源

当前使用的页面：

```text
https://top.baidu.com/board?tab=realtime
```

实现方式：

- 不是解析 DOM class，而是直接解析页面里的 `<!--s-data:{...}-->` 结构化 JSON。
- 这样比纯 HTML 选择器更稳定。

解析字段：

- `word`
- `query`
- `desc`
- `hotScore`
- `url`
- `appUrl`
- `isTop`
- `hotChange`

### 3.3 没有采用的来源

当前没有把百度普通网页搜索结果页作为核心来源，原因是：

- 更容易触发验证码
- 返回结构不稳定
- 做成本地 CLI 时可维护性较差

### 3.4 GitHub 来源

#### A. GitHub Trending

用途：

- `github`

当前使用的页面：

```text
https://github.com/trending
```

实现方式：

- 直接抓取 GitHub Trending HTML
- 从每个仓库卡片中解析仓库名、描述、语言、总 Stars、Forks、今日新增 Stars

当前输出的项目信息包括：

- 仓库名，例如 `owner/repo`
- 仓库链接
- 仓库描述
- 编程语言
- 总 Stars
- Forks
- 今日新增 Stars

## 4. 类别是怎么判断出来的

## 4.1 `us-hot`

判断方式：

- 主体由 Google Trends US 返回的热门趋势决定
- 当默认 `soft` 过滤后数量不足时，会补充少量 Google News Top Stories

结论：

- `us-hot` 是“来源定义型类别”
- 不是靠关键词检索定义出来的
- 但在过滤场景里，存在“Google Trends 主源 + Google News 回补”的补量逻辑

## 4.2 `china-hot`

判断方式：

- 不做本地分类
- 直接以百度热榜实时榜为准

结论：

- `china-hot` 也是“来源定义型类别”

## 4.3 `ai`

判断方式由两部分组成：

### Google 侧

- 用固定查询词去 Google News RSS Search 搜索
- 查询词本身定义了“AI 类别”的边界

### Baidu 侧

Baidu 侧不是语义模型判断，而是直接用百度热榜实时榜做关键词过滤。

AI 关键词目前包括：

```text
ai
artificial intelligence
openai
anthropic
gemini
nvidia
人工智能
大模型
机器人
智能体
```

只要标题或摘要中命中这些词，就会被视为 AI 相关。

## 4.4 `finance`

判断方式也分 Google 和 Baidu 两侧：

### Google 侧

- 用固定金融查询词去 Google News 搜索

### Baidu 侧

Baidu 侧采用规则过滤，不是语义分类：

1. 抓取百度热榜实时榜
2. 再从百度热榜里筛选出命中金融关键词的条目

金融关键词目前包括：

```text
stock
market
nasdaq
dow
s&p
fed
finance
financial
earnings
inflation
金融
财经
股市
美股
a股
黄金
油价
银行
基金
人民币
债
```

这意味着：

- “油价上涨” 会被识别为金融/财经相关
- “美股”“股市”“银行”“基金” 也会被纳入

这是一种启发式规则分类，不是语义推理，因此可能存在：

- 误报：例如某条热榜只是顺带提到油价
- 漏报：例如金融事件没有出现上述关键词

## 4.5 `us-market`

判断方式与 `finance` 类似，但关键词和查询更偏美股：

Google 查询词：

```text
"US stocks" OR "stock market" OR Nasdaq OR "S&P 500" OR "Dow Jones"
```

Baidu 关键词：

```text
美股
纳指
道指
标普
nasdaq
dow
s&p
股票
股指
```

## 4.6 `github`

`github` 不做本地主题分类，而是直接把 GitHub Trending 页面中的热门仓库卡片作为结果。

判断方式：

- 不做关键词或语义分类
- 直接以 GitHub Trending 页面顺序为准

## 4.7 `search`

`search` 是动态类别，不预设固定主题，且当前只通过 Google 查询。

Google 侧：

- 直接用用户输入的查询词做 Google News RSS Search

额外逻辑：

- `--google-locale auto` 时，如果查询里包含中文字符，则自动选 `cn`
- 否则自动选 `us`

## 5. 多来源结果是如何排序的

这是一个很关键的点。

## 5.1 单来源时

单来源的顺序完全遵循上游原始顺序：

- Google Trends：按 RSS 原顺序
- Google News：按 RSS 原顺序
- GitHub Trending：按页面原始顺序
- 百度热榜：按热榜原顺序

`us-hot` 在开启过滤时有一个例外：

- 先保留 Google Trends 中未被过滤的条目
- 如果还不够 `limit`，再按 Google News Top Stories 的原始顺序追加回补条目

## 6. 正文抓取是怎么做的

这是一个可选功能，只有显式传入 `--fetch-body` 才会启用。

执行时机：

- 先完成抓取
- 再完成标签过滤
- 如果是 `us-hot`，先做 Google News Top Stories 回补
- 最后只对“最终保留结果”的链接抓正文

实现方式：

- 使用 Playwright Chromium 无头模式
- Google News RSS 跳转链接会先等待重定向到真实文章页
- 百度搜索页会优先尝试打开首条结果页
- 之后从 `article / main / body` 等候选节点中抽取最长正文文本

限制：

- `github` 预设暂不抓正文
- 个别站点会出现验证码、反爬或拒绝访问，此时会在结果里返回正文抓取失败原因
- 抓取正文会显著增加响应时间，因此默认关闭

## 5.2 百度专题混合时

对于 `ai` / `finance` / `us-market` 的 Baidu 侧，排序规则是：

1. 先从百度热榜中过滤出命中关键词的条目
2. 再按命中分数和原始热榜顺序排序

其中内部排序规则是：

1. 先按关键词命中数量从高到低排序
2. 分数相同则按原始热榜排名排序

## 5.3 Google + Baidu 同时存在时

多来源聚合不会简单把 Google 全放前面再截断。

当前实现使用“轮询合并”：

1. 先取 Google 第 1 条
2. 再取 Baidu 第 1 条
3. 再取 Google 第 2 条
4. 再取 Baidu 第 2 条
5. 依此类推

这样做的目的：

- 避免一个来源把另一个来源完全挤掉
- 在小 `limit` 情况下也能同时看到 Google 和 Baidu

## 6. 语义标签与过滤

这是当前版本新增的一层本地处理逻辑，位于“抓取完成、输出之前”。

### 6.1 使用的后端

- `model`
  - 模型：`intfloat/multilingual-e5-small`
  - 用途：把 `title + summary + publisher` 编码成向量，再与预定义标签描述做相似度比较
- `tfidf`
  - 不依赖大模型
  - 使用固定标签原型文本、少量词表、TF-IDF 向量和 LogisticRegression 分类器完成分类
  - 训练语料由 `model` 伪标注样本和少量补充合成样本组成

因此：

- 默认推荐 `tfidf`
- 想要更强语义能力时用 `model`
- 想要更轻、更快、零模型下载时用 `tfidf`

两种后端都使用同一套标签定义，区别只在于打标方式。

### 6.2 当前标签集合

当前只保留 5 个主标签：

- `macro`：宏观、政策、监管、国际局势
- `industry`：公司、商业、产业、供应链、财报
- `tech`：AI、芯片、软件、开源、研发
- `public`：公共事务、法律、灾害、安全、民生
- `soft`：猎奇八卦、个体纠纷、情绪化社会新闻、低信息量内容

每条结果只会写入一个主标签，并带一个相似度分数。

### 6.3 默认行为

- 默认仅 `us-hot` / `china-hot` 触发 `soft` 过滤
- `ai` / `finance` / `us-market` / `github` / `search` 默认不启动分类
- `--no-filter` 会直接关闭过滤链路，此时不会做额外抓取或分类
- `--no-semantic` 会完全跳过语义模型
- `--filter-mode tfidf` 会切到轻量 TF-IDF 过滤器

### 6.4 为什么这样设计

目标不是做细粒度新闻学分类，而是优先过滤掉“没有明显认知增量”的内容。

例如这类内容通常会被压到 `soft`：

- 猎奇个案
- 情绪化冲突
- 婚恋家事
- 纯流量型社会热搜

## 7. 去重规则

当前去重是“标题归一化去重”，不是语义去重。

归一化规则：

- 去掉首尾空白
- 折叠多余空格
- 做 `casefold`

也就是说：

- 大小写差异会被认为是同一条
- 语义相近但标题不同，不会去重

## 8. 降级与补全策略

## 8.1 Baidu 专题筛选

对于 `ai` / `finance` / `us-market`：

1. 抓取百度热榜实时榜
2. 对标题和摘要做关键词匹配
3. 输出命中的热榜条目

## 8.2 上游失败处理

如果某个来源失败：

- 不会让整个命令直接失败
- 只会在该分组的 `warnings` 里记录错误
- 其他来源仍然照常输出

这意味着：

- `ai --source all` 时，哪怕百度失败，只要 Google 成功，仍会有结果
- `summary` 中某一组失败，不会拖垮其他组

## 9. 输出字段说明

每条 `NewsItem` 目前包含这些字段：

| 字段 | 含义 |
| --- | --- |
| `title` | 标题 |
| `category` | 所属类别 |
| `provider` | 来源大类，`google`、`baidu` 或 `github` |
| `feed` | 具体来源名，如 `Google News`、`Baidu Hotboard`、`GitHub Trending` |
| `link` | 跳转链接 |
| `summary` | 摘要或补充标题 |
| `publisher` | 发布方或来源说明 |
| `published_at` | 发布时间，已转成本地时区字符串 |
| `rank` | 在来源中的顺位 |
| `hot_score` | 百度热榜热度值 |
| `approx_traffic` | Google Trends 的近似热度 |
| `search_query` | 保留字段，当前默认不使用 |
| `language` | GitHub Trending 仓库语言 |
| `repo_stars` | GitHub 仓库总 Stars |
| `repo_forks` | GitHub 仓库 Forks |
| `stars_today` | GitHub Trending 今日新增 Stars |
| `content_label` | 语义主标签键，如 `macro`、`soft` |
| `content_label_name` | 语义主标签中文名 |
| `content_label_score` | 标签相似度分数 |
| `tags` | 附加标签，如 `新`、`热`、`置顶` |

分组级字段新增：

| 字段 | 含义 |
| --- | --- |
| `semantic_enabled` | 是否启用语义打标 |
| `semantic_model` | 当前使用的语义后端或模型标识 |
| `filter_enabled` | 是否启用语义过滤 |
| `excluded_labels` | 当前排除的标签 |
| `filtered_count` | 本次被过滤掉的条数 |

## 10. `--source` 参数的真实语义

| 参数 | 含义 |
| --- | --- |
| `auto` | 用该预设推荐来源 |
| `all` | 用该预设支持的全部来源 |
| `google` | 只用 Google |
| `baidu` | 只用 Baidu |
| `github` | 只用 GitHub Trending |

注意：

- 不是所有预设都支持 Google、Baidu 和 GitHub 双来源
- 例如 `us-hot` 只支持 `google`
- `china-hot` 只支持 `baidu`
- `github` 只支持 `github`

默认条数：

- 大多数预设默认返回 5 条
- `github` 默认返回 10 条

## 11. 为什么没有用更复杂的语义分类

当前版本没有引入 embedding/NLI/LLM 语义分类，原因是：

- 目标是一个轻量 CLI
- 希望尽量只用标准库和公开可访问接口
- 规则分类更可控、更容易解释
- 不增加模型部署成本

这意味着当前实现更偏：

- 来源定义
- 查询定义
- 关键词过滤

而不是：

- 向量相似度分类
- 零样本 NLI 分类
- 大模型语义判别

## 12. 当前实现的优点和局限

### 优点

- 轻量，无需额外模型依赖
- 安装简单
- 结果可解释
- 多来源聚合逻辑清晰
- 失败时能局部降级

### 局限

- `finance` / `ai` / `us-market` 的 Baidu 侧判断是启发式，不是语义理解
- `github` 依赖 GitHub Trending 页面结构，若页面结构变化需要更新解析逻辑
- 标题去重不是语义去重
- Google News 的标题切分使用的是最后一个 `" - "`，极少数情况下可能误分发布方
- 上游接口结构若变化，需要更新解析逻辑

## 13. 适合后续演进的方向

如果以后要继续增强，建议优先考虑：

1. 引入 embedding 作为二级语义过滤器
2. 对 `finance` / `ai` 加更细的白名单和黑名单
3. 给 `search` 增加导出与缓存能力
4. 增加导出 Markdown / JSON 文件能力
5. 增加定时任务输出日报

---

这份文档描述的是当前仓库实现，而不是一个抽象设计草案。如果代码后续有改动，这份文档也应同步更新。
