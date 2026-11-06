# SPDX-License-Identifier: GPL-3.0-or-later
"""站点清单发现测试：只用内联 HTML，不发真实请求。

模块命名为 ``site_io`` 而非 ``site``，避免遮蔽标准库 ``site``。
"""
import urllib.error

import pytest

from site_io import FetchError, declared_total, paper_url, parse_matrix_links

# 真实结构：单元格里是 <a class="prob-link">题量</a>
MATRIX_HTML = """
<table class="matrix-table"><tbody>
 <tr><td class="year-label">2004</td>
  <td><a href="/kaoyan/public/paper/%E6%95%B0%E5%AD%A6%E4%B8%80/2004/" class="prob-link">23</a></td></tr>
 <tr><td class="year-label">2099</td>
  <td><a href="/kaoyan/public/paper/%E6%95%B0%E5%AD%A6%E4%B8%80/2099/" class="prob-link">22</a></td>
  <td><a href="/kaoyan/public/paper/%E6%95%B0%E5%AD%A6%E4%BA%8C/2099/" class="prob-link">22</a></td>
  <td><a href="/kaoyan/public/paper/%E6%95%B0%E5%AD%A6%E4%B8%89/2099/" class="prob-link">21</a></td></tr>
</tbody></table>
<a href="/kaoyan/public/matrix/">真题矩阵</a>
"""


def test_parse_matrix_links_decodes_subject_and_count():
    links = parse_matrix_links(MATRIX_HTML)
    by_key = {(p['subject'], p['year']): p for p in links}
    assert by_key[('数学一', 2004)]['declared'] == 23
    assert by_key[('数学三', 2099)]['declared'] == 21
    assert all(p['url'].startswith('https://mathabc.xyz/kaoyan/public/paper/')
               for p in links)


def test_year_range_not_hardcoded():
    """2099 这种未来年份也必须出现，证明清单来自页面本身。"""
    years = {p['year'] for p in parse_matrix_links(MATRIX_HTML)}
    assert 2099 in years and 2004 in years


def test_dedup_and_sort_by_year_desc():
    links = parse_matrix_links(MATRIX_HTML + MATRIX_HTML)
    assert len(links) == 4
    assert [p['year'] for p in links] == [2099, 2099, 2099, 2004]
    assert links[0] == {'subject': '数学一', 'year': 2099, 'declared': 22,
                        'url': paper_url('数学一', 2099)}


def test_declared_total():
    assert declared_total(parse_matrix_links(MATRIX_HTML)) == 22 + 22 + 21 + 23


def test_paper_url_percent_encoded():
    assert paper_url("数学一", 2024) == (
        "https://mathabc.xyz/kaoyan/public/paper/%E6%95%B0%E5%AD%A6%E4%B8%80/2024/"
    )


def test_parse_matrix_links_no_matches():
    assert parse_matrix_links("<html><body>无链接</body></html>") == []


def test_plain_td_without_anchor_not_counted():
    """裸 <td>22</td> 不是题量单元；只有 prob-link 锚点文字才算。"""
    assert parse_matrix_links('<td>22</td>') == []


def test_fetch_error_carries_url(monkeypatch):
    import site_io

    def boom(*a, **kw):
        raise urllib.error.URLError('timed out')

    monkeypatch.setattr(site_io.urllib.request, 'urlopen', boom)
    with pytest.raises(FetchError) as exc:
        site_io.fetch('https://mathabc.xyz/x/')
    assert 'https://mathabc.xyz/x/' in str(exc.value)
    assert isinstance(exc.value, RuntimeError)


def test_list_papers_uses_matrix_url(monkeypatch):
    import site_io

    seen = []

    def fake_fetch(url):
        seen.append(url)
        return MATRIX_HTML

    monkeypatch.setattr(site_io, 'fetch', fake_fetch)
    assert len(site_io.list_papers()) == 4
    assert seen == [site_io.MATRIX_URL]
