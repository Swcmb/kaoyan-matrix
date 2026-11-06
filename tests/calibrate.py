# SPDX-License-Identifier: GPL-3.0-or-later
"""阈值与召回标定：按真实输入形态度量，并把「同题并列」判为正确。

为什么不能只看 top1：实测 1569 题里 583 题（37%）的归一化文本与其他题完全相同
（数一二三大量共用同题）。此时 top1 落在并列的另一张卷上，返回结果依然正确。

输入形态取四种真实会发生的：原文照贴、凭记忆手打（公式转 unicode）、
连选项一起贴、只记得前半句（按句子边界切，不按字符位置切）。

用法：python tests/calibrate.py [--sample 80]
输出：.cache/calibration.json
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import index  # noqa: E402
import match as match_mod  # noqa: E402
from match import search  # noqa: E402
from normalize import normalize  # noqa: E402

_LATEX = re.compile(r'\$[^$]*\$')
# 前半句切分点：中文句子边界
_CLAUSES = re.compile(r'[。；！？]')


def v_verbatim(rec):
    return rec['stem']


def v_unicode(rec):
    """凭记忆手打：把 $...$ 里的 LaTeX 就地转成 unicode 骨架，其余保持人话。"""
    return _LATEX.sub(lambda m: normalize(m.group(0)), rec['stem'])


def v_with_options(rec):
    return rec['stem'] + ' ' + ' '.join(rec['options'])


def v_first_clause(rec):
    """只记得前半句：在第一个句子边界或「则」处切断。"""
    stem = rec['stem']
    cut = len(stem)
    for pat in (_CLAUSES, re.compile(r'则')):
        m = pat.search(stem[10:])
        if m:
            cut = min(cut, 10 + m.end())
    return stem[:cut] if cut < len(stem) else stem


VARIANTS = {'verbatim': v_verbatim, 'unicode': v_unicode,
            'with_options': v_with_options, 'first_clause': v_first_clause}


def is_twin(a, b):
    """同一道题出现在多张卷上：归一化文本相同即视为等价正确答案。"""
    return a['norm'] == b['norm'] and a is not b


def evaluate(records, target, query):
    res = search(records, query, top_k=5)
    hits = res['hits']
    if not hits:
        return {'found': False, 'rank': None, 'top1_ok': False,
                'exact_pure': True, 'exact': False, 'len': len(normalize(query))}
    ok = lambda h: h['record'] is target or is_twin(h['record'], target)
    rank = next((i for i, h in enumerate(hits) if ok(h)), None)
    # 只看精确命中的集合：不足 5 条时用弱候选补齐是预期行为，不算误报
    exact_pure = all(ok(h) for h in hits if h['match'] == 'exact')
    hit = hits[0] if rank is None else hits[rank]
    return {'found': rank is not None, 'rank': rank, 'top1_ok': rank == 0,
            'exact_pure': exact_pure, 'exact': hit['match'] == 'exact',
            'len': len(normalize(query)), 'ratio': round(hit['ratio'], 4)}


def spliced_fake(records, rng):
    """跨题拼接的假题干：一半来自一道题，一半来自另一道题，不该判成精确命中。"""
    a, b = rng.sample(records, 2)
    return a['stem'][: len(a['stem']) // 2] + b['stem'][len(b['stem']) // 2:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=80)
    ap.add_argument('--seed', type=int, default=20261106)
    args = ap.parse_args()

    records = index.load()['records']
    rng = random.Random(args.seed)
    picks = rng.sample(records, args.sample)

    buckets = {k: {'n': 0, 'found': 0, 'top1': 0, 'exact_pure': 0, 'exact': 0,
                   'min_ratio': None} for k in VARIANTS}
    misses = []
    for target in picks:
        for name, fn in VARIANTS.items():
            query = fn(target)
            if len(normalize(query)) < match_mod.MIN_QUERY_LEN:
                continue
            r = evaluate(records, target, query)
            b = buckets[name]
            b['n'] += 1
            b['found'] += r['found']
            b['top1'] += r['top1_ok']
            b['exact_pure'] += r['exact_pure']
            b['exact'] += r['exact']
            ratio = r.get('ratio')
            if ratio is not None:
                b['min_ratio'] = (ratio if b['min_ratio'] is None
                                  else min(b['min_ratio'], ratio))
            if not r['found'] or not r['exact_pure']:
                misses.append({'variant': name, 'found': r['found'], 'rank': r['rank'],
                               'target': f"{target['year']}{target['subject']}"
                                         f"{target['num']}",
                               'qlen': r['len'], 'query': query[:70]})

    fake_exact, fake_ratios, fake_n = 0, [], 0
    for _ in range(30):
        q = spliced_fake(records, rng)
        if len(normalize(q)) < match_mod.MIN_QUERY_LEN:
            continue
        fake_n += 1
        res = search(records, q, top_k=5)
        if res['hits']:
            fake_ratios.append(round(max(h['ratio'] for h in res['hits']), 4))
            fake_exact += sum(1 for h in res['hits'] if h['match'] == 'exact')

    n_all = sum(b['n'] for b in buckets.values())
    report = {
        'sample': args.sample, 'seed': args.seed, 'records': len(records),
        'queries': n_all,
        'overall': {
            'found_in_top5': round(sum(b['found'] for b in buckets.values()) / n_all, 4),
            'top1_or_twin': round(sum(b['top1'] for b in buckets.values()) / n_all, 4),
            'exact_precision': round(
                sum(b['exact_pure'] for b in buckets.values()) / n_all, 4),
            'exact_on_target': round(sum(b['exact'] for b in buckets.values()) / n_all, 4),
        },
        'per_variant': {k: dict(
            n=v['n'],
            found_in_top5=round(v['found'] / v['n'], 4),
            top1_or_twin=round(v['top1'] / v['n'], 4),
            exact_precision=round(v['exact_pure'] / v['n'], 4),
            exact_on_target=round(v['exact'] / v['n'], 4),
            min_ratio=v['min_ratio'],
        ) for k, v in buckets.items()},
        'fake': {'queries': fake_n, 'exact_hits': fake_exact,
                 'max_ratio': max(fake_ratios, default=None)},
        'threshold_in_use': match_mod.FUZZY_THRESHOLD,
        'misses': misses[:12],
    }
    report['verdict'] = _verdict(report)
    out = Path(__file__).resolve().parent.parent / '.cache' / 'calibration.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    shown = dict(report)
    shown.pop('misses')
    shown.pop('verdict')
    print(json.dumps(shown, ensure_ascii=False, indent=2))
    print('\nverdict:', report['verdict'])
    if misses:
        print(f'\n未达标样例（{len(misses)} 条，前 6）：')
        for m in misses[:6]:
            print(' ', m)
    print(f'\n→ 写入 {out}')
    return 0 if report['verdict'] else 1


def _verdict(report):
    o = report['overall']
    return (o['found_in_top5'] >= 0.95 and o['top1_or_twin'] >= 0.85
            and o['exact_precision'] >= 0.95 and o['exact_on_target'] >= 0.9
            and report['fake']['exact_hits'] == 0)


if __name__ == '__main__':
    raise SystemExit(main())
