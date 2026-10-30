# 搜索站点契约（`a2-search` 的站点由你自己配置）

`a2-search` **不内置任何资源站**。它有两种源，一行一个写在 `~/.aria2/search-sites.conf`
（`A2_SITES_CONF` 可换路径；文件不存在时首次运行会生成模板）：

| 形式 | 写法 | 适合 |
|---|---|---|
| HTML 结果页 | `site=<名字>\|<URL 模板>` | 站点搜索结果页里直接有 `magnet:` 链接（多数索引站/论坛） |
| 命令 | `site=<名字>\|cmd:<命令>` | 站点要登录/Cookie、JS 渲染、有 API，或你想自己解析 |

另有一行 `websearch=<URL 模板>`：**全网发现**用，一个通用搜索页（默认 Bing 的 HTML 端点），
`a2-search --discover "<关键词>"` 用它列结果页链接。

模板占位符（两种源都支持）：

- `{query}` = URL 编码后的关键词（可安全拼进 URL / 命令）
- `{page}` = 页码，从 1 起；不写占位符时，HTML 模式会把关键词加在 URL 尾部，
  命令模式会把关键词作为**最后一个参数**追加，同时给环境变量 `A2_QUERY` / `A2_PAGE` / `A2_PAGES`

## 1. 配置示例

```ini
# ~/.aria2/search-sites.conf
site=某站|https://example.org/search?q={query}&page={page}
site=本地演示|cmd:python3 ~/.aria2/search-source-demo.py
websearch=https://www.bing.com/search?q={query}
proxy=http://127.0.0.1:7897          # 可选：抓取走代理（环境变量 A2_SEARCH_PROXY 优先）
```

`install-a2.sh` 会把模板装到 `~/.aria2/search-sites.conf`，并把两个示例源脚本放进 `~/.aria2/`：

| 文件 | 用途 |
|---|---|
| `~/.aria2/search-source-demo.py` | **离线自测源**：不联网，返回内置示例行，验证「搜 → 选 → 下」整条流程 |
| `~/.aria2/search-source-template.py` | **接入骨架**：填站点 URL 与解析函数即可 |

看当前配置了哪些源：`a2-search sites`。

## 2. HTML 模式怎么抽

- 只认页面里的 `magnet:?xt=urn:btih:…` 链接；**没有磁力链接的页面不会被猜**（不猜网页里的种子文件名）；
- 标题取该链接的可见文字（`<a href="magnet:…">标题</a>`），取不到就取最近的一段文字；
- 体积取本条链接附近的行内窗口（上一条的体积不会被算到这一条头上）；
- 做种数只在同一行内出现 `SE 12` / `seeds: 12` / `种子 12` 这类写法时才有，否则留空
  （留空**不参与** `--min-seeds` 过滤）；
- 一行一个磁力、多条重复时按 infohash 去重；
- 抓取用 `urllib`，默认跟你系统的 `http_proxy/https_proxy`；要指定代理：配置里写 `proxy=…`
  （或环境变量 `A2_SEARCH_PROXY`，优先级更高）。超时 `A2_SEARCH_TIMEOUT`（默认 20 秒）。

**JS 渲染、Cloudflare 挑战、需要登录的站点，HTML 模式拿不到东西**——这类改用 `cmd:` 源
（自己请求 API 或带 Cookie 抓页面），或换站点。抓不到时脚本会明确说「0 条磁力」，不会伪装成「没有这个资源」。

## 3. cmd 模式的输出契约（唯一硬性要求）

命令把结果以 **JSON 打到 stdout**：数组，或 `{"rows": [...]}`（也认 `results` / `data`）。

- stdout **只允许**出现 JSON；日志、进度、警告全部走 stderr
- 失败就**非零退出**（`a2-search` 会把退出码与 stderr 末尾原样报给用户，并给命令打码）
- 单行只要「标题 + 磁力或 infohash」两样就能用，其余字段缺失都不致命

| 字段 | 必需 | 说明 / 别名 |
|---|---|---|
| `title` | ✅ | 种子名称（别名 `name`）。缺失的行会被丢弃，统计里体现 |
| `magnet` | 二选一 | 完整磁力，别名 `magnet_uri` / `magnet_link` |
| `info_hash` | 二选一 | 32/40 位 hex，别名 `infohash` / `ih` / `hash`。脚本会拼成 `magnet:?xt=urn:btih:…`，可选带 `trackers` |
| `size_bytes` | 可选 | 字节数（别名 `bytes`/`length`）；也可用 `size`（数字=字节，字符串=`"3.5 GB"`）或 `size_gb` |
| `seeders` / `leechers` | 可选 | 别名 `seeds`/`s`、`leech`/`l`；缺失的行不参与 `--min-seeds` |
| `category` | 可选 | 别名 `cat`。写 `Movies`/`TV` 时直接用；留空则**按标题猜**（整季/年份/分辨率等正则） |
| `url` | 可选 | 详情页地址（别名 `detail`/`link`/`page`） |
| `source` | 可选 | 源名（别名 `src`/`site`/`indexer`），只用于显示 |

一行最小示例：

```json
[{"title": "Some.Show.S01.1080p.WEB-DL", "info_hash": "0123456789abcdef0123456789abcdef01234567",
  "size_bytes": 25769803776, "seeders": 18, "category": "TV"}]
```

## 4. 结果怎么用

```bash
a2-search 关键词                    # 默认过滤：电影全留、剧集要「整季/全集」且不是单集、噪音词剔除
a2-search 关键词 --all              # 放宽到全部分类（含单集；噪音词仍剔除）
a2-search 关键词 --pages 3          # 每个源多翻几页（某页没新内容就停）
a2-search 关键词 --site 某站         # 只查一个源
a2-search 关键词 --json             # 完整行（含 magnet），选哪条自己定
a2-search --discover 关键词          # 全网发现：列出结果页链接
```

- **没有缓存、没有序号**：每次都是现抓，`--json` 里的 `magnet` 直接往下走：
  `a2-verify "<magnet>"`（验真做种，0/1）→ `a2 add --dir "$(a2-dest check "$(a2-dest media)/TV")" "<magnet>"`
- 过滤与排序都在搜索侧（分类判定见下）；`--res` / `--min-seeds` / `--prefer` 可叠加：
  - 电影分类 → 直接留；剧集分类 → 必须命中「整季/全集」且不是单集 `SxxExx`；其它分类 → 默认不要
  - 分类来源：源给的 `category`，没给就按标题猜（`S01E02`/`S01`/`第N季`/`全N集`/`合集`/`Season N` → TV；
    年份或 `1080p` 等 → Movies）
- 落点仍由技能决定（`a2-dest check` 负责建目录/挂载/空间），a2 只下到 `--dir`；资源好坏用 `a2-verify` 判。

## 5. 写自己的 cmd 源（要点）

照 `search-source-template.py` 填三处：`SEARCH_URL` / `REQUEST_HEADERS`（UA、Cookie）、`parse()`。

- **别把过滤写进源**：过滤、排序都由 `a2-search` 统一做，源只管"如实返回站点给了什么"；
- **站点写 0 条要当错误报**：结构变了/被 WAF 拦时非零退出并说明，而不是打空数组
  （空数组在脚本那边看起来就是"确实没这个资源"）；
- **搜索语言跟着站点走**：很多站点只认真英文关键词；
- 需要 Cookie/登录态：放进 `REQUEST_HEADERS`，别把凭据写进命令行参数（会出现在 `ps` 里）；
  配置里确实要放 token 时 `chmod 600 ~/.aria2/search-sites.conf`，脚本打印命令时会自动打码，
  `A2_SEARCH_DEBUG=1` 才显示原文。

## 6. 排查

| 现象 | 原因 / 处理 |
|---|---|
| `还没有配置站点：…` | `search-sites.conf` 里没有 `site=` 行。加一行，或先用 `a2-search --discover` |
| `没有抓到任何磁力链接` | 结果页没有 `magnet:` 链接（JS 渲染/需要登录/结构变了）。换 URL、换站点或写 `cmd:` 源 |
| `抓取失败（HTTP 403/429/…）` | 站点反爬。放慢、换站点、或给抓取加代理 `A2_SEARCH_PROXY=…` |
| `抓取失败（<urlopen error …>）` | 网络不通/需要代理/DNS 问题。`A2_SEARCH_DEBUG=1` 看 URL，必要时设代理 |
| `搜索源失败（exit 3）：…` | cmd 源自己退出了。先单独在终端跑一遍那条命令 |
| `搜索源输出不是 JSON（…）` | 源把日志/HTML 打到 stdout 了。日志走 stderr，stdout 只留 JSON |
| `搜索源超时` | 源卡住（网络慢/站点无响应）。不加占位符时关键词作为最后一个参数追加，确认脚本收到了 |
| `抓到 N 条磁力，但没有一条通过默认过滤` | 过滤生效了。`--all` 放宽分类、`--min-seeds 0` 放宽做种数、`--res` 去掉分辨率限制 |
| `没有叫 '…' 的站点` | `--site` 名字要和 `search-sites.conf` 里 `site=` 的名字一致（区分大小写）；`a2-search sites` 看列表 |
| `没有配置 websearch=` | `--discover` 需要一行 `websearch=<搜索页 URL 模板>` |
