# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTP 与页面清单发现。

清单来自 ``/kaoyan/public/matrix/`` 页面上的链接本身，不硬编码年份与科目，
站点新增年份后无需改代码。模块名用 ``site_io`` 而非 ``site``，避免遮蔽标准库 ``site``。
"""
import re
import urllib.error
import urllib.parse
import urllib.request

__all__ = ["BASE", "MATRIX_URL", "FetchError", "fetch", "paper_url",
           "parse_matrix_links", "list_papers"]

BASE = "https://mathabc.xyz"
MATRIX_URL = BASE + "/kaoyan/public/matrix/"
UA = "Mozilla/5.0 (X11; Linux x86_64) kaoyan-matrix-mcp/0.1"
TIMEOUT = 40

_RE_PAPER = re.compile(
    r'href="/kaoyan/public/paper/([^/"]+)/(\d{4})/"[^>]*>(\d+)</a>')


class FetchError(RuntimeError):
    """单次页面请求失败，携带 URL 便于点名报错。"""

    def __init__(self, url: str, reason: str):
        super().__init__(f'抓取失败 {url}: {reason}')
        self.url = url
        self.reason = reason


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read().decode('utf-8')
    except (urllib.error.URLError, OSError, UnicodeDecodeError) as exc:
        raise FetchError(url, str(exc)) from exc


def paper_url(subject: str, year: int) -> str:
    return f'{BASE}/kaoyan/public/paper/{urllib.parse.quote(subject)}/{year}/'


def parse_matrix_links(html: str) -> list[dict]:
    """matrix 页表格单元格 → 试卷清单。

    单元格形如 ``<a href="/kaoyan/public/paper/数学一/2026/" class="prob-link">22</a>``，
    链接文字就是该卷声明的题量，一并取出供建库时逐卷核对。
    返回按年份降序、同年按页面出现顺序，去重。
    """
    seen: dict[tuple[str, int], dict] = {}
    for raw_subject, raw_year, declared in _RE_PAPER.findall(html or ''):
        subject = urllib.parse.unquote(raw_subject)
        key = (subject, int(raw_year))
        seen.setdefault(key, {
            'subject': subject, 'year': int(raw_year),
            'url': paper_url(*key), 'declared': int(declared),
        })
    return sorted(seen.values(), key=lambda p: -p['year'])


def declared_total(papers: list[dict]) -> int:
    return sum(p['declared'] for p in papers)


def list_papers() -> list[dict]:
    return parse_matrix_links(fetch(MATRIX_URL))
