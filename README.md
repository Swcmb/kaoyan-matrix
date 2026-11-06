# kaoyan-matrix · 考研数学真题定位 MCP

给一段考研数学题干，返回它是**哪一年、数学几、第几题**。

站点本身没有搜索接口，题干只散落在 69 张按年份和科目组织的试卷页里。本工具把这一整套试卷抓成本地索引，之后查询完全离线，并把带 LaTeX 的原文与凭记忆手打的纯文本折叠成同一种可比形式。

实测精度（见下文「精度数据」）：320 次真实输入查询中，目标题出现在前 5 个候选的比例为 **100%**，首位命中或落在同题孪生上的比例为 **99.7%**。

## 功能

- **按题干反查出处**：年份、科目（数学一/二/三）、题号、题型、分值、详情页链接。
- **四种输入形态都可用**：站点原文（含 LaTeX）、手打纯文本（`λ`、`∫`、`x^2`）、连 A/B/C/D 选项一起粘贴、只记得前半句。
- **诚实的不确定标注**：每条候选带 `match`（`exact` / `fuzzy` / `weak`）与 0—1 的 `confidence`；题干太短或没有可靠匹配时明确说"未找到"，给出候选但不冒充结论。
- **离线可用**：首次查询联网建库（69 个请求，实测 5—20 秒，取决于网络），之后不再需要网络。
- **改版防护**：逐卷核对解析题量与站点声明题量，任一卷不符即中止建库并保留旧索引。

## 环境要求

- Python 3.11+
- `mcp >= 2.2, < 3`（其余依赖全部来自 Python 标准库）

```bash
pip install "mcp>=2.2,<3"
```

## 安装

```bash
git clone <本仓库地址>
cd kaoyan-matrix
python server.py        # 以 stdio 启动 MCP 服务
```

## 接入 MCP 客户端

在客户端的 MCP 配置里加入（Claude Code、Codex、opencode、Cursor 等 stdio 客户端通用）：

```json
{
  "mcpServers": {
    "kaoyan-matrix": {
      "command": "python",
      "args": ["/绝对路径/kaoyan-matrix/server.py"]
    }
  }
}
```

## 用法

```python
find_problem(stem, subject=None, year=None, top_k=3)
refresh_index()
```

`stem` 为题干文本；`subject` 可选「数学一/二/三」缩小范围；`year` 可选限定年份。

输出示例（查询为 2024 年一道指数分布的选择题）：

```json
{
  "verdict": "题干精确匹配到 2 道题（同一道题常同时出现在数学一/二/三中，需一并参考）：2024 年数学一第10题、2024 年数学三第10题",
  "reason": "ok",
  "hits": [
    {"year": 2024, "subject": "数学一", "num": 10, "type": "选择题", "score": "5分",
     "url": "https://mathabc.xyz/kaoyan/problem/458/",
     "match": "exact", "confidence": 1.0, "ratio": 1.0,
     "stem_preview": "题目原文前 90 字，超出部分以省略号收尾…"}
  ],
  "index": {"built_at": 1793958624, "records": 1569, "pages": 69,
            "stale": false, "degraded": false}
}
```

`reason` 取 `ok` / `too_short`（题干信息量不足，拒答）/ `no_match`（无可靠匹配，候选仅供参考）。

## 精度数据

标定脚本 `tests/calibrate.py` 从索引随机抽 80 道题，每题生成四种真实输入形态（原文、转纯文本、连选项、前半句），共 320 次查询；另造 30 条跨题拼接的假题干做反例。随机种子 20261106，全量索引 1569 题，Python 3.13。

| 指标 | 值 | 含义 |
|---|---|---|
| recall@5 | 1.000 | 目标题出现在前 5 候选内 |
| top1 或同题孪生 | 0.997 | 首位即答案，或首位是同一道题在另一张卷上的副本 |
| `exact` 标签准确率 | 0.963 | 被标为精确命中的候选中确实是目标或其孪生的比例 |
| 假题干误标 `exact` | 0 / 30 | 拼接出的不存在的题不会被判成精确命中 |

"同题孪生"是语料本身的性质：1569 道题里有 583 道（37%）的归一化文本与另一张卷的题目完全相同——数学一/二/三大量共用同一道题。此时首位落在孪生题上，返回结果依然正确，因此指标以"目标或孪生"计。

单次查询在全库 1569 条上暴力打分耗时约 48 ms，这个规模下倒排索引和向量检索都换不到可感知的收益，所以没有引入。

## 工作原理

关键在归一化。站点题干形如 `$\displaystyle\int_{0}^{x} \mathrm{e}^{\cos t} \mathrm{~d} t$`，用户手打形如 `∫₀ˣ e^cos t dt`。不做命令映射时，同一道真题的匹配分会退化到与错误候选不可分（实测 0.491 对 0.216）；映射后能精确包含。

1. `normalize.py`：NFKC 折叠全角与上下标 → 展开 `\frac{a}{b}` → 剥离 `\begin/\end` 与装饰命令 → 222 项命令映射表还原符号与希腊字母 → 删除定界符、标点、运算符与空白 → 小写。
2. `match.py`：`score = 4×开头命中 + 2×精确命中 + 覆盖度 + 0.5×相似度`。开头命中单独加权，因为题型相同的题目常有完全相同的开头短句，同一句开头能落进几十道题的题干里；精确命中还要求查询覆盖该题干长度的 50% 以上，否则 `exact` 标签的准确率从 0.96 掉到 0.60。
3. `index.py`：从 matrix 页链接发现试卷清单（不硬编码年份，站点新增年份后无需改代码），并发抓取、逐卷核对题量、原子写缓存。

## 配置项

| 环境变量 | 作用 | 默认 |
|---|---|---|
| `KAOYAN_MATRIX_CACHE` | 覆盖索引缓存文件路径 | `<代码所在目录>/.cache/index.json`（随 `server.py` 的位置走，与启动时的当前工作目录无关） |

缓存目录建议加入 `.gitignore`：其中是站点题目的全文快照，属运行时数据。

## 测试与验证

```bash
python -m pytest tests/ -q        # 57 个测试函数，参数化展开后 71 个用例
python tests/calibrate.py         # 精度标定，写 .cache/calibration.json
python tests/smoke_stdio.py       # 完整 MCP stdio 协议端到端
python tests/acceptance.py        # 逐项验收账本
```

`tests/acceptance.py` 的六项验收全部通过：测试全绿、建库条数与站点声明题量总和逐卷相符、两种输入形态首位精确命中、编造题干不出现 `exact`、MCP 协议子进程实跑退出码 0。

测试文件不保存任何站点真题原文，需要真实题干时一律运行时从索引读取。

## 故障排查

| 现象 | 原因与处理 |
|---|---|
| 启动报 `ModuleNotFoundError: mcp.server.mcpserver` | mcp 版本低于 2.2。`pip install "mcp>=2.2,<3"` |
| 首次查询慢 | 正常，正在抓取 69 张试卷页建库，实测 5—20 秒 |
| 返回 `degraded: true` | 重建失败，本次结果来自旧缓存。检查网络，或调 `refresh_index()` |
| 建库报"解析题量与声明题量不一致" | 站点结构变化。旧缓存仍可用，需按新结构更新 `parser.py` |
| `reason: too_short` | 题干太短。补充到至少 6 个归一化字符，理想是一整句 |
| 结果有多条 | 同一道题出现在多张卷上，属正常结果，应一并参考 |

## 数据来源与使用边界

题目内容来自 <https://mathabc.xyz/kaoyan/public/matrix/>（页面标注 © mathabc.xyz 杨世显，渝ICP备2026008344号）。本仓库只在运行时抓取，不分发题目全文：`.cache/` 不进版本控制，唯一入库的测试素材 `tests/fixtures/synthetic_paper.html` 是手写的 DOM 骨架，文本全部自造。使用时请遵守目标站点的使用条款。

## License

GPL-3.0-or-later，见 [COPYING](COPYING)。
