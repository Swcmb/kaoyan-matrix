# SPDX-License-Identifier: GPL-3.0-or-later
"""工具层冒烟：直接调用两个工具，打印真实输出（验收证据之一）。

本文件不保存任何站点真题原文：查询串一律运行时从索引取，
编造题干由本文件自造（站点并不存在该题）。
用法：python tests/smoke_tools.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import index  # noqa: E402
import server  # noqa: E402
from normalize import normalize  # noqa: E402

_LATEX_SPAN = re.compile(r'\$[^$]*\$')

# 自造的假题干：站点上不存在这道题，用来验证不会误报精确命中
FAKE = ('设椭球面 x^2+2y^2+3z^2=6 与参数为 7 的泊松分布相切于点 (1,1,1)，'
        '求其主轴长度、偏度系数与协方差矩阵行列式之积')


def plain(stem: str) -> str:
    """把 LaTeX 行内公式转成纯文本，模拟凭记忆手打的输入。"""
    return _LATEX_SPAN.sub(lambda m: normalize(m.group(0)), stem)


def pick(records, year, subject, num):
    return next(r['stem'] for r in records
                if r['year'] == year and r['subject'] == subject and r['num'] == num)


def show(title, res, limit=3):
    print('=' * 72)
    print(f'[{title}]')
    print('verdict:', res['verdict'])
    print('reason:', res['reason'], '| query_len:', res['query_len'], '| index:', res['index'])
    for h in res['hits'][:limit]:
        print(f"  - {h['year']} {h['subject']} 第{h['num']}题 {h['type']} {h['score']}"
              f" match={h['match']} conf={h['confidence']} ratio={h['ratio']}")
        print(f"    {h['url']}")


def main() -> int:
    records = index.load()['records']
    full = pick(records, 2024, '数学一', 10)

    show('站点原文（含 LaTeX）', server.find_problem(full))
    show('手打纯文本', server.find_problem(plain(full)))
    show('只有前半句', server.find_problem(full[:40]))
    show('限定年份 + 限定科目',
         server.find_problem(plain(full), year=2024, subject='数学一'))
    show('编造的不存在题干', server.find_problem(FAKE))
    show('题干过短', server.find_problem('曲线'))
    show('连选项一起粘贴', server.find_problem(
        full + ' ' + ' '.join(next(r['options'] for r in records
                                   if r['stem'] == full))))

    print('=' * 72)
    meta = server.refresh_index()
    print('[refresh_index]', meta)

    print('=' * 72)
    try:
        server.find_problem('   ')
    except Exception as exc:
        print('空题干 ->', type(exc).__name__, exc)
    print('top_k=99 钳制后命中数:',
          len(server.find_problem(full, top_k=99)['hits']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
