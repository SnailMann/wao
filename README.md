# daily-cli

`daily-cli` 是一个面向 Linux / macOS 的命令行工具，用来快速拉取每日热门信息，重点覆盖：

- 美国热门事件
- 中国热门事件
- AI 发展趋势
- 金融热门事件
- GitHub Trending
- 额外附带一个 `us-market` 预设，方便快速查看美股焦点

它参考了你给的 `daily-news` 思路，但做了几处增强：

- 改成可安装的 Python 包，支持 `pip install .`
- Google 侧使用当前可用的 Trends RSS / Google News RSS
- Baidu 侧使用百度热榜结构化数据与关键词过滤
- 默认使用 `intfloat/multilingual-e5-small` 做语义打标
- 默认过滤 `soft` 标签，尽量屏蔽低信息量内容
- `summary` / 多 preset `fetch` 采用并行抓取 + 全局批量推理，减少重复模型开销
- 提供多命令、多预设、多输出格式

## 安装

要求 Python 3.10+。

```bash
python3 -m pip install .
daily-cli model download
```

安装后可直接使用：

```bash
daily-cli summary
```

如果你更喜欢隔离式安装，也可以：

```bash
python3 -m pip install pipx
pipx install .
```

## 命令

### 1. 一次看默认五类信息

```bash
daily-cli summary
daily-cli summary --no-filter
```

### 2. 拉取指定预设

```bash
daily-cli fetch us-hot
daily-cli fetch china-hot ai finance
daily-cli fetch github --limit 10
daily-cli fetch us-market --source all --limit 8
```

可用预设：

- `us-hot`: 美国热门事件
- `china-hot`: 中国热门事件
- `ai`: AI 发展趋势
- `finance`: 金融热门事件
- `github`: GitHub Trending
- `us-market`: 美股焦点

### 3. 自定义关键词查询

```bash
daily-cli search OpenAI
daily-cli search 人工智能 --google-locale cn
daily-cli search 美股 --format json
```

### 4. 查看支持的预设

```bash
daily-cli presets
```

## 常用参数

```bash
--source auto|google|baidu|github|all
--limit N
--timeout 10
--format text|json
--no-semantic
--no-filter
--exclude-label soft
--semantic-model-dir /path/to/model
```

说明：

- `auto`: 使用该预设推荐的来源
- `all`: 聚合该命令支持的全部来源
- `google`: 仅 Google
- `baidu`: 仅 Baidu
- `github`: 仅 GitHub Trending

默认条数：

- 大多数预设默认返回 5 条
- `github` 默认返回 10 条

默认语义行为：

- `summary` / `fetch` / `search` 默认都会做语义打标
- 默认过滤 `soft` 标签
- 如果只想看标签、不做过滤，使用 `--no-filter`
- 如果想完全关闭语义能力，使用 `--no-semantic`

`search` 命令还支持：

```bash
--google-locale auto|us|cn
```

## 示例

```bash
daily-cli model download
daily-cli summary --limit 5
daily-cli summary --no-filter
daily-cli fetch ai finance --source all
daily-cli fetch china-hot --exclude-label soft --exclude-label public
daily-cli fetch github --limit 10
daily-cli fetch china-hot --format json
daily-cli search "Federal Reserve" --google-locale us
daily-cli search "人工智能"
```

## 设计说明

- `us-hot` 默认使用 Google Trends RSS，因为它更适合美国热门事件。
- `china-hot` 默认使用百度热榜结构化数据。
- `ai` / `finance` 默认聚合 Google News RSS 与百度热榜过滤结果。
- `github` 使用 GitHub Trending 页面抓取热门项目、语言、Stars、Forks 和今日新增 Stars。
- 语义标签默认使用 `intfloat/multilingual-e5-small`，当前标签为 `macro`、`industry`、`tech`、`public`、`soft`。
- 所有预设默认过滤 `soft`，并在输出里直接展示语义标签和分数。
- Baidu 普通网页搜索较容易触发验证码，因此没有把它作为核心依赖接口。

更详细的类别、来源、排序和降级逻辑说明见：

- [docs/NEWS_PIPELINE.md](./docs/NEWS_PIPELINE.md)

## 测试

```bash
python3 -m unittest discover -s tests -v
```
