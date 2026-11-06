# SPDX-License-Identifier: GPL-3.0-or-later
"""规格 §13 验收：逐条执行并打出验证账本。任何一条不达标即非零退出。"""
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import index  # noqa: E402
import server  # noqa: E402
import site_io  # noqa: E402
from normalize import normalize  # noqa: E402

_LATEX_SPAN = re.compile(r'\$[^$]*\$')

rows = []


def check(no, name, ok, evidence):
    rows.append((no, name, bool(ok), evidence))
    return ok


# 1 pytest 全绿（规格 §13.1）
_sub = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-q'], cwd=str(ROOT),
                      capture_output=True, text=True, timeout=900)
check(1, 'pytest 全绿', _sub.returncode == 0,
      _sub.stdout.strip().splitlines()[-1] if _sub.stdout.strip() else f'exit={_sub.returncode}')

# 2 refresh_index 条数与 matrix 声明题量总和一致，耗时 < 15s
t0 = time.time()
meta = server.refresh_index()
elapsed = round(time.time() - t0, 2)
papers = site_io.list_papers()
declared = site_io.declared_total(papers)
check(2, 'refresh_index 条数 == matrix 声明总和且 <15s',
      meta['records'] == declared and elapsed < 15 and meta['pages'] == len(papers),
      f'records={meta["records"]} declared={declared} papers={len(papers)} '
      f'seconds={elapsed} pages={meta["pages"]}')

recs = index.load()['records']
target = next(r for r in recs if r['year'] == 2024 and r['subject'] == '数学一'
              and r['num'] == 10)

# 3 站点原文（含 LaTeX）首位命中且 exact
res = server.find_problem(target['stem'])
top = res['hits'][0]
check(3, '站点原文（含 LaTeX）→ 2024 数学一 第10题 exact',
      (top['year'], top['subject'], top['num'], top['match']) ==
      (2024, '数学一', 10, 'exact') and top['type'] == '选择题' and top['score'] == '5分',
      f"verdict={res['verdict']} | top1={top['year']}{top['subject']}第{top['num']}题 "
      f"{top['type']}/{top['score']} conf={top['confidence']}")

# 4 去掉全部 LaTeX 后手打，仍首位命中同一题（运行时转换，测试文件不落真题原文）
hand = _LATEX_SPAN.sub(lambda m: normalize(m.group(0)), target['stem'])
res2 = server.find_problem(hand)
t2 = res2['hits'][0]
check(4, '手打无 LaTeX → 同一题 exact',
      (t2['year'], t2['subject'], t2['num'], t2['match']) ==
      (2024, '数学一', 10, 'exact'),
      f"reason={res2['reason']} top1={t2['subject']}第{t2['num']}题 conf={t2['confidence']}")

# 5 编造题干不出现 exact
fake = ('设椭球面 x^2+2y^2+3z^2=6 与参数为 7 的泊松分布相切于点 (1,1,1)，'
        '求其主轴长度、偏度系数与协方差矩阵行列式之积')
res3 = server.find_problem(fake)
check(5, '编造题干 → 无 exact 且 reason=no_match',
      all(h['match'] != 'exact' for h in res3['hits']) and res3['reason'] == 'no_match',
      f"reason={res3['reason']} hits={len(res3['hits'])} "
      f"match集合={sorted({h['match'] for h in res3['hits']})}")

# 6 完整 MCP 协议：以子进程实跑 smoke_stdio.py，用退出码与输出作为证据
# 6 完整 MCP 协议：以子进程实跑 smoke_stdio.py，用退出码与输出作为证据
proc = subprocess.run([sys.executable, str(ROOT / 'tests' / 'smoke_stdio.py')],
                      capture_output=True, text=True, timeout=240)
protocol_ok = (proc.returncode == 0
               and "tools: ['find_problem', 'refresh_index']" in proc.stdout
               and '第10题' in proc.stdout and '[B 空题干] is_error=True' in proc.stdout)
check(6, '完整 MCP stdio 协议实跑通过', protocol_ok,
      f'exit={proc.returncode} | ' + ' | '.join(
          l for l in proc.stdout.splitlines()
          if l.startswith('server:') or l.startswith('tools:')))

width = max(len(n) for _, n, _, _ in rows)
all_ok = True
for no, name, ok, ev in rows:
    all_ok &= ok
    print(f"[{'PASS' if ok else 'FAIL'}] {no}. {name:<{width}}")
    print(f"       {ev}")
print('\n总体：', 'ALL PASS' if all_ok else 'HAS FAILURE')
raise SystemExit(0 if all_ok else 1)
