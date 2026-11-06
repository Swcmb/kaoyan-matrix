# SPDX-License-Identifier: GPL-3.0-or-later
"""片段级检测：文件里是否含有任何真题题干连续片段（不只是完整题干）。

前一版检测只做「完整题干 norm 是否为文件文本子串」，会漏掉题干片段——
而手打查询、注释举例恰好都是片段。这里改为最长公共子串匹配。

阈值 16 字的依据：低于它开始命中通用题干套话（如「计算二重积分 … dxdy」
这类公共表达），那属于任何作者都会写下的功能性措辞，不构成分发他人内容；
16 字以上才可能是某道题特有的表述。发布前用默认 16 复核，
想更严格可临时降到 12 并逐条人工判断是否真是题目专述。

用法：python tests/scan_stems.py [--min-len 16]
"""
import argparse
import difflib
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from normalize import normalize  # noqa: E402


def longest_common(a: str, b: str) -> tuple[int, str]:
    """返回两串的最长公共子串长度与内容。"""
    match = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return match.size, a[match.a:match.a + match.size]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-len', type=int, default=16)
    ap.add_argument('--root', default='.')
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    cache = root / '.cache' / 'index.json'
    if not cache.exists():
        print('缺 .cache/index.json，先跑一次 refresh_index')
        return 2
    records = json.loads(cache.read_text(encoding='utf-8'))['records']

    files = [p for p in root.rglob('*')
             if p.is_file() and p.suffix in {'.py', '.md', '.html', '.toml', '.json'}
             and '.cache' not in p.parts and '__pycache__' not in p.parts
             and p.name != pathlib.Path(__file__).name]

    findings = defaultdict(list)
    for p in files:
        ftxt = normalize(p.read_text(encoding='utf-8', errors='replace'))
        if len(ftxt) < args.min_len:
            continue
        for r in records:
            n = r['norm']
            if len(n) < args.min_len:
                continue
            size, frag = longest_common(ftxt, n)
            if size >= args.min_len:
                findings[str(p)].append((size, frag,
                                         f"{r['year']} {r['subject']} 第{r['num']}题"))
    if not findings:
        print(f'片段级残留（阈值 {args.min_len} 字）: 无 ✓  扫描 {len(files)} 个文件')
        return 0
    for f, hits in sorted(findings.items()):
        hits.sort(key=lambda x: -x[0])
        best = hits[0]
        print(f'\n{f}\n   最长重合 {best[0]} 字  命中 {best[2]}\n   片段: {best[1]}')
        print(f'   该文件共 {len(hits)} 处超阈值重合')
    print(f'\n片段级残留文件数: {len(findings)}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
