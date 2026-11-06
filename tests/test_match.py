# SPDX-License-Identifier: GPL-3.0-or-later
"""匹配层测试：合成部分用 fixture，真实题干部分缺索引即 skip。

测试文件不保存任何站点真题原文，需要真实题干时一律运行时从索引读取。
"""
import pathlib
import re

import pytest

from match import search, FUZZY_THRESHOLD, MIN_QUERY_LEN
from normalize import normalize
from parser import parse_paper

# 行内公式片段，用于把 LaTeX 题干转成"手打纯文本"形态
_LATEX_SPAN = re.compile(r'\$[^$]*\$')

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "synthetic_paper.html").read_text(
    encoding="utf-8")
RECORDS = parse_paper(FIXTURE, subject="模拟一", year=2099)


def _hit(res):
    assert res['hits'], res
    return res['hits'][0]


def test_exact_containment_on_synthetic_stem():
    res = search(RECORDS, "曲线 $y=\\sin x$ 在点 $(0,0)$ 处的切线斜率为 ____ 。")
    assert _hit(res)['match'] == 'exact'
    assert _hit(res)['record']['num'] == 2


def test_latex_free_query_hits_same_item():
    res = search(RECORDS, "设样例函数 f(x)=x2+1 ，则下列结论正确的是")
    assert _hit(res)['match'] == 'exact'
    assert _hit(res)['record']['num'] == 1


def test_query_with_options_hits_via_hay():
    """用户连选项一起粘贴时，靠 hay 仍然精确命中。"""
    res = search(RECORDS, "设样例函数 $f(x)=x^{2}+1$ ，则下列结论正确的是 A $f(x)$ 为奇函数")
    assert _hit(res)['match'] == 'exact'


def test_prefix_only_query():
    res = search(RECORDS, "设样例函数 $f(x)=x^{2}+1$")
    assert _hit(res)['record']['num'] == 1


def test_short_query_rejects_fuzzy():
    """归一化后过短的题目只允许精确命中，避免乱匹配。"""
    assert len("曲线") < MIN_QUERY_LEN
    res = search(RECORDS, "曲线")
    assert res['hits'] == [] and res['reason'] == 'too_short'


def test_filter_year_excludes_everything():
    res = search(RECORDS, "设样例函数 $f(x)=x^{2}+1$ ，则下列结论正确的是", year=2000)
    assert res['hits'] == [] and res['reason'] == 'no_match'


def test_filter_subject_and_year_keep_match():
    res = search(RECORDS, "计算二重积分", year=2099, subject="模拟一")
    assert _hit(res)['record']['num'] == 3


def test_topk_and_monotonic_scores():
    res = search(RECORDS, "设样例函数 f(x)=x2+1", top_k=1)
    assert len(res['hits']) <= 1 + 7  # 并列并入上限见 match.MAX_TIE_EXTENSION
    scores = [h['score'] for h in res['hits']]
    assert scores == sorted(scores, reverse=True)


def test_tied_records_all_kept():
    """同题跨卷（分数完全相同）必须全部返回，不受 top_k 截断影响。"""
    twin = [dict(RECORDS[0]), dict(RECORDS[0])]
    twin[1]['subject'] = '模拟二'
    res = search(twin, "设样例函数 $f(x)=x^{2}+1$ ，则下列结论正确的是", top_k=1)
    assert len(res['hits']) == 2
    assert {h['record']['subject'] for h in res['hits']} == {'模拟一', '模拟二'}


def test_no_match_reason():
    res = search(RECORDS, "这道完全不相关的题目问的是天文学里的红移现象")
    assert res['reason'] == 'no_match'
    assert all(h['match'] != 'exact' for h in res['hits'])


def test_fuzzy_label_respects_threshold():
    res = search(RECORDS, "设样例函数 f(x)=x2+1 则下列结论正确")
    for h in res['hits']:
        if h['match'] == 'fuzzy':
            assert h['ratio'] >= FUZZY_THRESHOLD


def test_empty_records():
    assert search([], "任意一段足够长的题干文本")['reason'] == 'no_match'


# ---------------- 真实索引部分 ----------------

def _real_index():
    try:
        import index
        idx = index.load(auto_refresh=False)
        return idx['records'] if idx['meta'].get('records', 0) > 1000 else None
    except Exception:
        return None


REAL = _real_index()
needs_real = pytest.mark.skipif(REAL is None, reason='需要先构建真实索引')


def _target():
    return next(r for r in REAL if r['year'] == 2024 and r['subject'] == '数学一'
                and r['num'] == 10)


@needs_real
def test_real_stem_exact_hit():
    res = search(REAL, _target()['stem'])
    top = _hit(res)
    assert (top['record']['year'], top['record']['subject'], top['record']['num']) == (
        2024, '数学一', 10)
    assert top['match'] == 'exact'


def _plain(stem: str) -> str:
    """模拟"用户凭记忆手打、公式写成纯文本"这一输入形态。

    运行时从索引取题干再转换，测试文件里不保存任何站点原文。
    """
    return _LATEX_SPAN.sub(lambda m: normalize(m.group(0)), stem)


@needs_real
def test_real_stem_without_latex_exact_hit():
    assert _hit(search(REAL, _plain(_target()['stem'])))['match'] == 'exact'


@needs_real
def test_same_question_across_papers_returned():
    res = search(REAL, _plain(_target()['stem']), top_k=3)
    got = {(h['record']['subject'], h['record']['num']) for h in res['hits']}
    assert ('数学一', 10) in got and ('数学三', 10) in got


@needs_real
def test_prefix_of_real_stem_exact():
    res = search(REAL, _target()['stem'][:40])
    assert _hit(res)['record']['num'] == 10
