# SPDX-License-Identifier: GPL-3.0-or-later
"""产出可复现的性能与测试计数证据。

第一版 README 里的「48 ms」只测了 difflib 单项比值，不是 search() 的真实路径；
复审在另一台环境复测得到 2—5 倍差异。耗时随机器负载变化很大，因此这里同时落盘
测量环境，并在文档里以区间而非单点呈现。

用法：python tests/bench.py
输出：.cache/bench.json、.cache/pytest_collect.txt
"""
import json
import pathlib
import platform
import re
import statistics
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import index  # noqa: E402
import match  # noqa: E402

SAMPLES = 60


def measure_search(records):
    queries = [r['stem'][:60] for r in records[::17]][:SAMPLES]
    ts = []
    for q in queries:
        t = time.perf_counter()
        match.search(records, q, top_k=3)
        ts.append((time.perf_counter() - t) * 1000)
    ts.sort()
    return {
        'n': len(ts),
        'median_ms': round(statistics.median(ts), 1),
        'p90_ms': round(ts[int(len(ts) * 0.9)], 1),
        'min_ms': round(ts[0], 1),
        'max_ms': round(ts[-1], 1),
    }


def measure_build():
    t = time.perf_counter()
    meta = index.refresh()
    return {'seconds': round(time.perf_counter() - t, 2),
            'records': meta['meta']['records'], 'pages': meta['meta']['pages']}


def count_tests():
    """分别统计测试函数个数与 pytest 实际收集的用例数（参数化会展开）。"""
    funcs = 0
    for p in sorted((ROOT / 'tests').glob('test_*.py')):
        funcs += len(re.findall(r'^def test_', p.read_text(encoding='utf-8'), re.M))
    proc = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-q',
                           '--collect-only'], cwd=str(ROOT),
                          capture_output=True, text=True)
    cases = 0
    for line in proc.stdout.splitlines():
        m = re.search(r'(\d+) tests? collected', line)
        if m:
            cases = int(m.group(1))
    return funcs, cases


def main() -> int:
    records = index.load()['records']
    funcs, cases = count_tests()
    report = {
        'environment': {
            'platform': platform.platform(),
            'python': platform.python_version(),
            'cpu': platform.processor(),
            'machine': platform.machine(),
        },
        'records': len(records),
        'search': measure_search(records),
        'search_twice': measure_search(records),   # 第二次采样，用于说明波动幅度
        'build': measure_build(),
        'tests': {'functions': funcs, 'collected_cases': cases},
    }
    out = ROOT / '.cache'
    out.mkdir(exist_ok=True)
    (out / 'bench.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                    encoding='utf-8')
    (out / 'pytest_collect.txt').write_text(f'{funcs} {cases}\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    s1, s2 = report['search'], report['search_twice']
    print(f"\n两次采样中位：{s1['median_ms']} ms vs {s2['median_ms']} ms"
          f"（同机同索引，波动 {abs(s2['median_ms'] - s1['median_ms'])} ms）")
    print(f"建库：{report['build']['seconds']} s / {report['build']['records']} 条")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
