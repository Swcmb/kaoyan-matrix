# SPDX-License-Identifier: GPL-3.0-or-later
"""考研真题定位 MCP 服务：两个工具，逻辑全在各模块里，这里只做装配与结果整形。"""
import time

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import index
import match

INSTRUCTIONS = (
    '按题干定位考研数学真题的年份、科目与题号。'
    '数据源 https://mathabc.xyz/kaoyan/public/matrix/ 的 69 张试卷页，'
    '索引首次使用时抓取（约 5 秒）并落盘缓存，之后离线可用。'
    '输入可以是站点原文（含 LaTeX）、凭记忆手打（公式转纯文本）或只给前半句。'
    '同一道题常同时出现在数学一/二/三中，命中多条属正常结果，需一并告知用户。'
)

server = MCPServer('kaoyan-matrix', instructions=INSTRUCTIONS)

TOP_K_LIMIT = 10
PREVIEW_LEN = 90


def _preview(text: str) -> str:
    return text if len(text) <= PREVIEW_LEN else text[:PREVIEW_LEN] + '…'


def _meta(idx: dict) -> dict:
    meta = idx['meta']
    return {'built_at': meta['built_at'], 'records': meta['records'],
            'pages': meta['pages'], 'stale': meta.get('stale', False),
            'degraded': meta.get('degraded', False)}


def _describe(h: dict) -> str:
    return f"{h['year']} 年{h['subject']}第{h['num']}题"


def _verdict(hits: list, reason: str, query_len: int) -> str:
    if reason == 'too_short':
        return (f'题干归一化后仅 {query_len} 字，信息量不足以可靠判定，请补充更完整的题干')
    if not hits:
        return '未找到可靠匹配：索引中没有任何题目的题干与该查询精确或高度相似'
    exact = [h for h in hits if h['match'] == 'exact']
    if len(exact) == 1:
        h = exact[0]
        kind = f"（{h['type']} {h['score']}）" if h['type'] else ''
        return f'命中 {_describe(h)}{kind}，题干精确匹配'
    if exact:
        names = '、'.join(_describe(h) for h in exact[:5])
        return (f'题干精确匹配到 {len(exact)} 道题（同一道题常同时出现在数学一/二/三中，'
                f'需一并参考）：{names}')
    return (f'未找到精确匹配，仅给出 {len(hits)} 条相似候选，'
            f'不可直接当作结论，请核对候选题干')


def _to_hit(h: dict) -> dict:
    r = h['record']
    return {
        'year': r['year'], 'subject': r['subject'], 'num': r['num'],
        'type': r['type'], 'score': r['score'], 'url': r['detail_url'],
        'match': h['match'], 'confidence': h['confidence'],
        'ratio': h['ratio'], 'stem_preview': _preview(r['stem']),
    }


@server.tool()
def find_problem(stem: str, subject: str | None = None, year: int | None = None,
                 top_k: int = 3) -> dict:
    """给一段考研数学题干，返回它是哪一年、数学几、第几题。

    Args:
        stem: 题干文本，可以是站点原文（含 LaTeX）、纯文本手打，或只有前半句。
        subject: 可选，限定「数学一」「数学二」「数学三」之一以缩小范围。
        year: 可选，限定年份，例如 2024。
        top_k: 返回候选条数，1-10，默认 3。分数并列的同题跨卷结果会一并返回。

    Returns:
        verdict 一句话结论；hits 候选列表，每项含 year/subject/num/type/score/url/
        match/confidence/stem_preview；index 缓存元数据；reason 判定状态。
    """
    if not (stem or '').strip():
        raise ToolError('stem 不能为空：请粘贴或输入考研数学题干文本')
    limit = max(1, min(int(top_k), TOP_K_LIMIT))
    idx = index.load()
    res = match.search(idx['records'], stem, subject=subject, year=year, top_k=limit)
    hits = [_to_hit(h) for h in res['hits']]
    return {
        'verdict': _verdict(hits, res['reason'], res['query_len']),
        'reason': res['reason'],
        'query_len': res['query_len'],
        'hits': hits,
        'index': _meta(idx),
    }


@server.tool()
def refresh_index() -> dict:
    """强制重新抓取全部试卷页并重建索引缓存。站点新增年份或题目后调用。"""
    start = time.time()
    idx = index.refresh()
    meta = idx['meta']
    return {'records': meta['records'], 'pages': meta['pages'],
            'built_at': meta['built_at'], 'seconds': round(time.time() - start, 2),
            'cache': str(index.CACHE_PATH),
            'index_version': meta['parser_version']}


if __name__ == '__main__':
    server.run(transport='stdio')
