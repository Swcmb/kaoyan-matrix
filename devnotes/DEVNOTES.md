# DEVNOTES: kaoyan-matrix

> Developer notes. Not part of the published documentation.
> Snapshot: 2026-11-06 | branch main（首次发布） | commit 待生成 | OS Windows 11 26100 | runtime Python 3.13.9 + mcp 2.2.0

## 1. Local setup

- 依赖：`mcp>=2.2,<3` + Python 标准库（`urllib` / `re` / `json` / `difflib` / `unicodedata` / `concurrent.futures`）
- 安装命令：`pip install "mcp>=2.2,<3"`；测试另需 `pytest`
- 启动命令：`python server.py`（stdio）
- 数据目录：`<代码所在目录>/.cache/index.json`（约 1.1 MB，gitignore）。`index.py` 用模块自身的 `BASE_DIR` 定位，与启动时的当前工作目录无关
- 前置条件：首次建库需能访问 `mathabc.xyz`；之后离线
- 本机的 agent harness 同步副本（内部，仅本机路径，对外读者可忽略）：`D:/ai-configs/mcp/kaoyan-matrix/`，登记于 `D:/ai-configs/mcp/kaoyan-matrix.json`

## 2. Environment

| 变量 | 用途 | 本地来源 | 是否必需 |
|---|---|---|---|
| `KAOYAN_MATRIX_CACHE` | 覆盖索引缓存路径 | 默认 `<代码所在目录>/.cache/index.json` | 否 |

无凭据依赖：站点全部页面公开可读，无需 token、cookie 或账号。

## 3. Architecture notes

- 入口：`server.py`（只做 MCP 装配与结果整形，无业务逻辑）
- 主要组件：`site_io`（清单发现 + HTTP）→ `parser`（页面解析）→ `normalize`（归一化）→ `match`（打分）→ `index`（建库与缓存）
- 数据流：matrix 页 → 69 个试卷 URL + 每卷声明题量 → 并发抓取 → 结构化题目 → 归一化 → 落盘缓存 → 查询时全库暴力打分
- 与公开文档的差异：README 的精度数字来自 `--sample 80`（320 次查询）；本地另跑过 `--sample 40/60` 的中间结果，量级一致
- 站点侧的本地替身：无。测试用 `tests/fixtures/synthetic_paper.html` 手写骨架，真实页测试在缺缓存时自动 skip

## 4. Decisions

| 日期 | 决定 | 备选 | 理由 | 复查 |
|---|---|---|---|---|
| 2026-11-06 | 本地全量索引 + 字符串匹配 | n-gram/BM25 倒排；把页面交给调用方 agent 判断 | 1569 条规模暴力打分实测 48.5 ms，索引换不到收益；丢给 agent 每次烧数万 token 且结论不稳 | 题目总量增长 10 倍以上时重估 |
| 2026-11-06 | 用 mcp 2.x 原生 `MCPServer` | 锁 `mcp<2` 用 v1 `FastMCP` | 锁 v1 的前提是写 v1 风格代码；原生 v2 后该前提消失，且免掉一层隔离环境 | 客户端 SDK 生态若仍普遍停在 v1，则改回并双写兼容层 |
| 2026-11-06 | 精确命中要求覆盖度 ≥ 0.5 | 只要包含就算精确 | 公共开头短句会把几十道题一起标成 exact，`exact_precision` 0.96 → 0.60 | 语料出现更多短题干时重标阈值 |
| 2026-11-06 | 逐卷核对声明题量 | 只做 20% 总量漂移启发式 | 站点自己报告每卷题量，等于免费的完整性校验 | 站点改版去掉该数字时降级回漂移检查 |
| 2026-11-06 | 指标以"目标或同题孪生"计 | top1 唯一命中 | 实测 583/1569（37%）题干的归一化文本与另一张卷完全相同 | 若做同题合并去重，可回到唯一命中 |

## 5. Experiments and failures

| 日期 | 尝试 | 结果 | 失败原因 | 下一步 |
|---|---|---|---|---|
| 2026-11-06 | 直接把题干原文做字符串匹配 | 不可用 | 站点题干是 LaTeX，`\lambda` 与 `λ` 归一化后不等，正确项 0.491 与错误项 0.216 不可分 | 加命令映射表，做成 `normalize.py` 独立一层 |
| 2026-11-06 | 解析器按 `class="stem"` 匹配 | 22 题只解析出 10 题 | 填空题与解答题用 `class="stem stem-only"` | 正则放宽为 `class="stem[^"]*"`，并写回归测试 |
| 2026-11-06 | fixture 用 `div.choice-text` 造选项 | fixture 测试全绿，真实页选项数 0 | fixture 与真实 DOM 不符（真实是 `span.choice-label` + `span.choice-text` 成对） | 按真实结构重写 fixture；教训是 fixture 必须先对齐真实页面 |
| 2026-11-06 | 用 `difflib` 比值当对外置信度 | 输出 `confidence: 7.278` | 综合分量纲无意义 | 排序分与对外置信度分离，置信度约束到 0—1 |
| 2026-11-06 | 标定把题干按字符位置切片当扰动 | recall 只有 56% | 从 LaTeX 命令中间切断产生非法输入，且 top1 唯一命中指标本身错了 | 改成四种真实输入形态 + recall@K 指标 |
| 2026-11-06 | 检测真题原文残留（第一版） | 报 0 命中，误报为"干净" | 子串方向写反：应把文件全文当 haystack | 反向重测，查出 5 个文件含原文，随后全部改为运行时读取 |
| 2026-11-06 | 重跑 `build-mcp-merged.py` 以登记本服务 | 产生 293 行无关 churn | 该脚本读各客户端真实配置，不读 `mcp/*.json` | 回退合并文件；登记只需 `mcp/*.json` + `mcp-index.json` + 出处清单 |

## 6. Known issues

| 症状 | 可能原因 | 临时处理 | 相关链接 |
|---|---|---|---|
| 短题干（如一句话开头）返回多条 `exact` | 语料里存在公共开头短句 | 提高 `top_k` 并核对 `stem_preview`；或传 `year`/`subject` 缩小范围 | — |
| 2027 年及以后题目查不到 | 尚未建索引 | 调 `refresh_index()` | — |
| 站点整体改版导致建库中止 | 解析题量与声明题量不符 | 旧缓存仍可用；需更新 `parser.py` 选择器 | — |

## 7. TODO

- [ ] 同题合并：把归一化文本完全相同的记录折叠成一条多出处结果，让"唯一答案"指标重新可用
- [ ] 站点若提供 JSON 接口，替换 HTML 解析层（`parser.py` 可整体换掉，接口不变）
- [ ] 覆盖 2004 年前的真题（受限于站点是否收录）

## 8. Links

以下 `D:/ai-configs/...` 均为本机 harness 内部路径（内部，对外读者可忽略）。

- 公开文档：`README.md`
- 设计规格：`D:/ai-configs/project-context/specs/2026-11-06-kaoyan-matrix-mcp-design.md`
- 实现计划：`D:/ai-configs/project-context/plans/2026-11-06-kaoyan-matrix-mcp.md`
- harness 登记：`D:/ai-configs/mcp/kaoyan-matrix.json`、`D:/ai-configs/docs/mcp-sources.md`
- 数据源：https://mathabc.xyz/kaoyan/public/matrix/

## 9. Local change log

- 2026-11-06: 首次从 `D:/ai-configs/mcp/kaoyan-matrix/` 抽出独立仓库副本，README 按公开读者重写，测试与文档去除站点真题原文
