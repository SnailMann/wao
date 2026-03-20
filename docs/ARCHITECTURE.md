# daily Architecture

## 1. 目录目标

这次目录设计收敛成 6 个一眼能懂的概念：

- `cli`
- `core`
- `tools`
- `fetchers`
- `plugins`
- `common`

这样看代码时不需要再先理解一堆中间层名词。

## 2. 目录划分

```text
daily_cli/
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

## 3. 每层职责

### `cli`

只负责命令行入口：

- 参数解析
- help 面板
- 把参数交给核心逻辑

不直接处理上游数据。

### `core`

这是业务主干：

- `models.py`
  - `NewsItem` / `SectionResult`
- `specs.py`
  - `SourcePlan` / `CollectionSpec`
- `topics.py`
  - 业务 topic 注册表
- `subscriptions.py`
  - RSS 订阅定义和持久化逻辑
- `x_auth.py`
  - X token 管理
- `collector.py`
  - 把 provider / filter / enricher 串起来

一句话：`core` 负责“daily 到底怎么工作”。

### `tools`

这是原子工具层：

- `search.py`
- `trend.py`
- `rss.py`

它们是对外最直接、最稳定的能力入口。  
`summary` / `fetch` 这类组合命令则由 `cli + core.collector` 复用这些能力。

`subscriptions` 放在 `rss` 语义下面，而不是单独顶层命令，因为它本质上就是 feed 的保存和批量拉取。

### `plugins`

现在这里只放真正的插件能力。

- 注册表：
  - `filters.py`
- 实现：
  - `semantic.py`

目前只有一个过滤插件体系：

- `tfidf`
- `model`

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

### `common`

只放真正通用的东西：

- `config.py`
  - 配置目录与 JSON 文件读写
- `output.py`
  - text / json 渲染

它不承载业务规则。

## 4. 依赖方向

推荐理解成下面这条单向链：

`cli -> core -> fetchers/plugins -> common`

其中：

- `tools` 主要复用 `core`
- `plugins` 不应该反向依赖 `cli`
- `common` 尽量保持最底层

这样后续扩展时不容易长成环状依赖。

## 5. 扩展规则

后续新增功能时，优先按这个顺序放：

1. 新增业务 topic
   - 放到 `core/topics.py`
2. 新增原子命令能力
   - 放到 `tools/`
3. 新增来源或正文抓取
   - 放到 `fetchers/`
4. 新增过滤插件
   - 放到 `plugins/`
5. 新增纯通用工具
   - 放到 `common/`

## 6. 为什么这样更容易维护

因为现在每一层回答的问题都很明确：

- `cli`：用户怎么调用
- `core`：系统怎么编排
- `tools`：有哪些原子能力
- `fetchers`：数据从哪抓、怎么抓
- `plugins`：有哪些过滤插件
- `common`：哪些是通用支撑

这套命名本身就比之前的中间层目录更容易理解。
