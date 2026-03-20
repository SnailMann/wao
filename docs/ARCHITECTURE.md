# wao / 哇哦 Architecture

## 1. 目录目标

这次目录设计收敛成 5 个一眼能懂的概念：

- `cli`
- `service`
- `fetchers`
- `plugins`
- `core`

这样看代码时不需要再先理解一堆中间层名词。

## 2. 目录划分

```text
wao/
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

## 3. 每层职责

### `cli`

只负责命令行入口：

- `cli.py`
  - 顶层 help 和总路由网关
- `args.py`
  - CLI 公共参数与输出辅助
- 各一级命令文件
  - `topics.py` / `trend.py` / `summary.py` / `fetch.py` / `search.py` / `x.py` / `rss.py` / `model.py`

不直接处理上游数据。

### `service`

这是查询和编排主干：

- `collector.py`
  - 把 fetcher / filter / body enrich 串起来
- `topics.py`
  - 业务 topic 注册表
- `search.py` / `trend.py` / `rss.py`
  - 原子查询能力
- `subscriptions.py`
  - RSS 订阅定义和持久化逻辑

一句话：`service` 负责“如何把原子抓取能力组合成可调用服务”。

### `fetchers`

数据抓取都放这里，而且尽量按来源拆文件；浏览器型正文抓取再下沉到 `crawlers/` 子包。

- `google.py`
- `baidu.py`
- `github.py`
- `x.py`
- `rss.py`
- `body.py`
- `crawlers/base.py`
- `crawlers/playwright.py`
- `common.py`
- `registry.py`

这样以后维护某个来源时，直接进对应文件就行；如果是浏览器抓取能力，就进 `crawlers/`，不会和普通源抓取混在一起。

### `plugins`

现在这里只放真正的插件能力。

- 注册表：
  - `filters.py`
- 实现：
  - `semantic.py`

目前只有一个过滤插件体系：

- `tfidf`
- `model`

### `core`

只放真正的核心基础能力：

- `models.py`
  - `NewsItem` / `SectionResult`
- `specs.py`
  - `SourcePlan` / `CollectionSpec`
- `config.py`
  - 配置目录与 JSON 文件读写
- `output.py`
  - text / json 渲染
- `x_auth.py`
  - X token 管理

## 4. 依赖方向

推荐理解成下面这条单向链：

`cli -> service -> fetchers/plugins -> core`

其中：

- `service` 负责配置和编排 fetcher / plugin
- `plugins` 不应该反向依赖 `service` 或 `cli`
- `core` 尽量保持最底层

这样后续扩展时不容易长成环状依赖。

## 5. 扩展规则

后续新增功能时，优先按这个顺序放：

1. 新增业务 topic
   - 放到 `service/topics.py`
2. 新增原子查询能力
   - 放到 `service/`
3. 新增来源或正文抓取
   - 放到 `fetchers/`
4. 新增过滤插件
   - 放到 `plugins/`
5. 新增基础模型 / 配置 / 公共输出
   - 放到 `core/`

## 6. 为什么这样更容易维护

因为现在每一层回答的问题都很明确：

- `cli`：用户怎么调用
- `service`：系统怎么编排和暴露查询能力
- `fetchers`：数据从哪抓、怎么抓
- `plugins`：有哪些过滤插件
- `core`：哪些是底层核心支撑

这套命名本身就比之前的中间层目录更容易理解。
