# SPDX-License-Identifier: GPL-3.0-or-later
"""题干 → 题目记录的匹配打分。纯函数，不碰网络与缓存。

两段式：先看归一化后的精确包含，再用 difflib 比值精排。
1569 条规模下全库暴力打分为百毫秒量级（同机重复采样中位 112—218 ms，负载相关，见 tests/bench.py），该规模无需倒排索引。
"""
import difflib

from normalize import normalize

__all__ = ["search", "FUZZY_THRESHOLD", "MIN_QUERY_LEN", "MAX_TIE_EXTENSION",
           "MIN_COVERAGE"]

# 0.55 由 tests/calibrate.py 的扰动/拼接分布确认：真扰动样本的 ratio 明显高于
# 跨题拼接假题干的上界，两者之间存在空隙。改动前请重跑标定。
FUZZY_THRESHOLD = 0.55
MIN_QUERY_LEN = 6
# 非开头命中要被判为精确命中，查询至少要覆盖该题干归一化长度的这个比例。
# 0.5 由标定数据决定：低于它时，公共开头短句会把几十道题一起标成 exact，
# exact_precision 从 0.96 掉到 0.60。
MIN_COVERAGE = 0.5
MAX_TIE_EXTENSION = 7


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _pool(records, subject, year):
    if subject is not None:
        records = [r for r in records if r['subject'] == subject]
    if year is not None:
        records = [r for r in records if r['year'] == year]
    return records


def _confidence(exact: float, prefix: float, ratio: float) -> float:
    """0-1 的置信度，与 score 分离：score 只用于排序，量纲对外没有意义。"""
    if exact and prefix:
        return 1.0
    if exact:
        return 0.92
    if ratio >= FUZZY_THRESHOLD:
        return round(min(0.88, 0.4 + 0.6 * ratio), 3)
    return round(ratio * 0.6, 3)


def search(records, query: str, subject: str | None = None, year: int | None = None,
           top_k: int = 3) -> dict:
    """→ {'hits': [Hit], 'reason': str, 'query_len': int}

    Hit = {'record', 'exact': bool, 'prefix': bool, 'ratio': float,
           'score': float, 'confidence': float, 'match': str}
    reason ∈ 'ok' / 'too_short' / 'no_match'。
    """
    pool = _pool(records, subject, year)
    qn = normalize(query)
    if not pool:
        return {'hits': [], 'reason': 'no_match', 'query_len': len(qn)}
    if len(qn) < MIN_QUERY_LEN:
        # 太短的题干信息量不足，只承认精确包含；这里连包含都无从判定，直接拒绝
        return {'hits': [], 'reason': 'too_short', 'query_len': len(qn)}

    scored = []
    for r in pool:
        hay, norm = r.get('hay') or r['norm'], r['norm']
        contained = qn in hay or (norm and norm in qn)
        # 开头命中是比任意位置命中更强的证据：用户粘贴的多半是题干起始。
        # 反过来，题型相同的题目常有完全相同的开头短句，同一句开头能落进几十道题的
        # 题干里，只靠任意位置包含会把它们全标成精确命中并扰乱排序。
        prefix = 1.0 if (hay.startswith(qn) or norm.startswith(qn)) else 0.0
        coverage = min(len(qn), len(hay)) / max(len(qn), len(hay), 1)
        exact = 1.0 if (prefix or (contained and len(qn) >= MIN_COVERAGE * len(norm))) else 0.0
        ratio = max(_ratio(qn, hay), _ratio(qn, norm))
        scored.append({
            'record': r,
            'exact': bool(exact),
            'prefix': bool(prefix),
            'ratio': round(ratio, 4),
            'score': round(4 * prefix + 2 * exact + coverage + 0.5 * ratio, 4),
            'confidence': _confidence(exact, prefix, ratio),
            'match': 'exact' if exact else ('fuzzy' if ratio >= FUZZY_THRESHOLD else 'weak'),
        })

    scored.sort(key=lambda h: -h['score'])
    limit = max(1, min(top_k, 10))
    hits = scored[:limit]
    # 同一道题常同时出现在数一/数三等多张卷上，分数完全相同，全部保留。
    # 只并入 exact 的并列项：weak 候选凑数没有意义，只会增加噪音。
    if hits and hits[-1]['match'] == 'exact':
        cut = hits[-1]['score']
        for extra in scored[limit:limit + MAX_TIE_EXTENSION]:
            if extra['score'] != cut or extra['match'] != 'exact':
                break
            hits.append(extra)

    reason = 'ok' if any(h['match'] in ('exact', 'fuzzy') for h in hits) else 'no_match'
    return {'hits': hits, 'reason': reason, 'query_len': len(qn)}
