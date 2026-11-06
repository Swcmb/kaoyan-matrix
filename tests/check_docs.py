# SPDX-License-Identifier: GPL-3.0-or-later
"""文档与代码口径一致性检查。

设计要点：文件清单**自动发现**，绝不写死文件名。第一版把待查文件硬编码成
README/DEVNOTES/server.py 三个，结果漏掉了 index.py 里过时的耗时与离线宣称，
让一次复审直接 FAIL。教训是：检查器的覆盖面本身就是它最可能出错的地方。

用法：python tests/check_docs.py
退出码非 0 表示存在必须修的问题。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUFFIXES = {'.py', '.md', '.toml', '.html', '.json', '.cfg', '.ini', '.txt'}
SKIP_DIR_PARTS = {'.cache', '__pycache__', '.pytest_cache', '.git', '.egg-info'}
SELF = pathlib.Path(__file__).resolve().name

# 已被实测推翻或语义错误的宣称：出现即阻断
STALE = [
    (r'约 5 秒|5\.0 s|约 6 秒', '建库耗时已改为实测区间 5—20 秒'),
    (r'完全离线|之后不再需要网络|之后查询完全离线',
     '索引有 7 天 TTL，超期需联网重建，措辞必须反映降级语义'),
    (r'150 项命令映射', '映射表实为 222 项'),
    (r'48\.5 ms|约 48 ms', '该数字只测了 ratio 单项，非 search() 真实路径'),
    (r'默认 \./\.cache|\| `?\./\.cache', '缓存随模块 BASE_DIR，不是当前工作目录'),
]
# 用户写作规则禁止的否定式对比修辞
NEGATION = r'不是[^。；，\n]{1,24}[，,]\s*(?:而)?是'


def discover():
    out = []
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.suffix not in SUFFIXES:
            continue
        if any(part in SKIP_DIR_PARTS for part in p.parts):
            continue
        if p.name == SELF:      # 本文件把这些字符串作为检测模式列出，需排除自身
            continue
        out.append(p)
    return sorted(out)


def main() -> int:
    files = discover()
    problems, notes = [], []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding='utf-8', errors='replace')
        for pat, why in STALE:
            for m in re.finditer(pat, text):
                line = text[:m.start()].count('\n') + 1
                problems.append(f'{rel}:{line} 过时宣称「{m.group(0)}」——{why}')
        for m in re.finditer(NEGATION, text):
            line = text[:m.start()].count('\n') + 1
            problems.append(f'{rel}:{line} 否定式对比修辞「{m.group(0)}」')

    rd = (ROOT / 'README.md').read_text(encoding='utf-8')
    if 'devnotes' in rd.lower():
        problems.append('README.md 链接了 devnotes/，公开文档不得指向开发者笔记')

    # 交叉核对：README 声称的测试数量与 pytest 实际收集数
    collected = (ROOT / '.cache' / 'pytest_collect.txt')
    if collected.exists():
        claimed = re.findall(r'(\d+) 个测试函数.*?(\d+) 个用例', rd)
        actual = collected.read_text(encoding='utf-8').split()
        if claimed and len(claimed[0]) == 2:
            f, c = int(claimed[0][0]), int(claimed[0][1])
            if [f, c] != [int(x) for x in actual[:2]]:
                problems.append(f'README 测试数 {f} 函数/{c} 用例 与实测 '
                                f'{actual[0]}/{actual[1]} 不符')
            else:
                notes.append(f'README 测试数与实测一致：{f} 函数 / {c} 用例')
    else:
        notes.append('缺 .cache/pytest_collect.txt，未核对测试数量（先跑 bench.py）')

    notes.append(f'扫描文件数：{len(files)}（自动发现，含全部源文件与文档）')
    for n in notes:
        print('  ·', n)
    if problems:
        print('\n必须修：')
        for q in problems:
            print('  ✗', q)
        return 1
    print('\n口径一致性：通过 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
