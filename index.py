# SPDX-License-Identifier: GPL-3.0-or-later
"""全量索引的构建、缓存与改版防护。

站点无搜索接口，题干只存在于 69 张试卷页里，因此索引靠一次并发抓取建立：
实测 5.0 s / 1569 题 / 约 1 MB，之后查询完全离线。
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import site_io
from parser import parse_paper

__all__ = ["BuildError", "cache_path", "load", "refresh", "PARSER_VERSION", "TTL_DAYS"]

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / '.cache'
PARSER_VERSION = '2'  # 归一化改为迭代到不动点后递增，旧缓存自动失效
TTL_DAYS = 7
MAX_WORKERS = 8
DRIFT_LIMIT = 0.20


class BuildError(RuntimeError):
    """建库失败：页面结构变化、解析为空或请求失败。抛出时旧缓存保持不动。"""


def cache_path() -> Path:
    override = os.environ.get('KAOYAN_MATRIX_CACHE')
    return Path(override) if override else CACHE_DIR / 'index.json'


CACHE_PATH = cache_path()


def _read_cache() -> dict | None:
    try:
        return json.loads(CACHE_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _fetch_one(url: str) -> str:
    """单页抓取，失败重试一次；最终失败即中止整个建库，绝不产出缺页的半份索引。"""
    try:
        return site_io.fetch(url)
    except site_io.FetchError:
        try:
            return site_io.fetch(url)
        except site_io.FetchError as exc:
            raise BuildError(str(exc)) from exc


def _check_drift(count: int) -> None:
    old = _read_cache()
    if not old:
        return
    prev = old.get('meta', {}).get('records', 0)
    if prev and abs(count - prev) / prev > DRIFT_LIMIT:
        raise BuildError(
            f'题目总数从 {prev} 变为 {count}，偏离超过 20%，判定站点结构变化，保留旧缓存')


def build() -> dict:
    papers = site_io.list_papers()
    if not papers:
        raise BuildError('matrix 页没有解析出任何试卷链接，判定站点结构变化')
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        pages = list(pool.map(_fetch_one, [p['url'] for p in papers]))

    records, empty, mismatch = [], [], []
    for paper, html in zip(papers, pages):
        got = parse_paper(html, paper['subject'], paper['year'])
        if not got:
            empty.append(f"{paper['subject']} {paper['year']} 解析出 0 题（{paper['url']}）")
        elif paper.get('declared') is not None and len(got) != paper['declared']:
            mismatch.append(f"{paper['subject']} {paper['year']}: 解析 {len(got)} 题，"
                            f"matrix 声明 {paper['declared']} 题")
        records.extend(got)
    if empty:
        raise BuildError('以下页面解析为空，判定站点结构变化：\n' + '\n'.join(empty))
    if mismatch:
        raise BuildError('解析题量与 matrix 声明题量不一致，判定站点结构变化，'
                         '保留旧缓存：\n' + '\n'.join(mismatch))

    _check_drift(len(records))
    meta = {
        'built_at': int(time.time()),
        'source': site_io.MATRIX_URL,
        'pages': len(papers),
        'records': len(records),
        'parser_version': PARSER_VERSION,
    }
    _atomic_write({'meta': meta, 'records': records})
    return {'meta': dict(meta, stale=False, degraded=False), 'records': records}


def _atomic_write(payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, CACHE_PATH)


def _stale(meta: dict) -> bool:
    age = time.time() - meta.get('built_at', 0)
    return age > TTL_DAYS * 86400


def _cached() -> dict | None:
    data = _read_cache()
    if not data or data.get('meta', {}).get('parser_version') != PARSER_VERSION:
        return None
    return {'meta': dict(data['meta'], degraded=False), 'records': data['records']}


def load(auto_refresh: bool = True) -> dict:
    """读缓存；缺失、parser_version 不符或超过 TTL 时重建。

    重建失败但旧缓存可用时降级返回旧数据并标 ``degraded``，这是查询能离线工作的关键。
    """
    cached = _cached()
    if cached and (not auto_refresh or not _stale(cached['meta'])):
        cached['meta']['stale'] = _stale(cached['meta'])
        return cached
    try:
        return build()
    except BuildError:
        if cached:
            cached['meta']['degraded'] = True
            cached['meta']['stale'] = _stale(cached['meta'])
            return cached
        raise


def refresh() -> dict:
    return build()
