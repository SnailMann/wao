# daily-cli

`daily-cli` 是一个面向 Linux / macOS 的命令行工具，用来快速拉取每日热门信息，重点覆盖：

- 美国热门事件
- 中国热门事件
- AI发展
- 金融热门事件
- GitHub Trending
- 额外附带一个 `us-market` 预设，方便快速查看美股焦点

它参考了你给的 `daily-news` 思路，但做了几处增强：

- 改成可安装的 Python 包，支持 `pip install .`
- Google 侧使用当前可用的 Trends RSS / Google News RSS
- Baidu 侧使用百度热榜结构化数据与关键词过滤
- 默认使用 `tfidf` 混合后端做过滤分类
- 默认仅在 `us-hot` 和 `china-hot` 里过滤 `soft` 标签
- 支持 `model` 和 `tfidf` 两种标签/过滤后端
- 只有真正启用过滤的 preset 才会触发额外抓取与分类
- 提供多命令、多预设、多输出格式

## 安装

要求 Python 3.10+。

```bash
python3 -m pip install .
daily-cli model download
```

如果你只打算使用 `--filter-mode tfidf`，可以不下载模型。

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
- `ai`: AI发展
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
--filter-mode model|tfidf
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

- 默认仅 `us-hot` / `china-hot` 会触发 `soft` 过滤
- `ai` / `finance` / `us-market` / `github` / `search` 默认不会启动分类
- 如果关闭过滤，使用 `--no-filter`，此时也不会做额外抓取或分类
- 如果想完全关闭语义能力，使用 `--no-semantic`
- 如果想切到轻量过滤器，使用 `--filter-mode tfidf`

`search` 命令还支持：

```bash
--google-locale auto|us|cn
```

## 示例

```bash
daily-cli model download
daily-cli summary --limit 5
daily-cli summary --no-filter
daily-cli summary --filter-mode tfidf
daily-cli fetch ai finance --source all
daily-cli fetch china-hot --exclude-label soft --exclude-label public
daily-cli fetch github --limit 10
daily-cli fetch china-hot --format json
daily-cli search "Federal Reserve" --google-locale us
daily-cli search "人工智能"
```

## 设计说明

- `us-hot` 默认使用 Google Trends RSS，因为它更适合美国热门事件。
- 当 `us-hot` 开启 `soft` 过滤且 Google Trends 保留下来的条目不足时，会按需用 Google News Top Stories 回补。
- `china-hot` 默认使用百度热榜结构化数据。
- `ai` / `finance` 默认聚合 Google News RSS 与百度热榜过滤结果。
- `github` 使用 GitHub Trending 页面抓取热门项目、语言、Stars、Forks 和今日新增 Stars。
- 标签分类保持为 `macro`、`industry`、`tech`、`public`、`soft`。
- 默认后端为 `tfidf`，也支持 `model` 后端。
- `tfidf` 后端内部使用 `TF-IDF + LogisticRegression + 少量词表` 的混合分类，训练语料由 `model` 伪标注样本和少量补充合成样本组成。
- 默认仅 `us-hot` / `china-hot` 过滤 `soft`，其他预设默认既不拦截，也不启动分类。
- Baidu 普通网页搜索较容易触发验证码，因此没有把它作为核心依赖接口。

更详细的类别、来源、排序和降级逻辑说明见：

- [docs/NEWS_PIPELINE.md](./docs/NEWS_PIPELINE.md)

## 测试

```bash
python3 -m unittest discover -s tests -v
```
