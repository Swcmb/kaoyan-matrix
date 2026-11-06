# SPDX-License-Identifier: GPL-3.0-or-later
"""索引层测试：全程 monkeypatch 网络，只验缓存与防护逻辑。"""
import json
import pathlib

import pytest

import index as index_mod
from site_io import FetchError

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "synthetic_paper.html").read_text(
    encoding="utf-8")


def _papers(n=2, declared=3):
    return [{'subject': '模拟一', 'year': 2099, 'url': f'https://x/p{i}',
             'declared': declared} for i in range(n)]


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(index_mod, 'CACHE_PATH', tmp_path / 'index.json')
    monkeypatch.setattr(index_mod, 'CACHE_DIR', tmp_path)
    yield


@pytest.fixture
def stub_network(monkeypatch):
    monkeypatch.setattr(index_mod.site_io, 'list_papers', lambda: _papers())
    monkeypatch.setattr(index_mod.site_io, 'fetch', lambda url: FIXTURE)


def test_build_from_stubbed_fetch(stub_network):
    idx = index_mod.refresh()
    # 2 张卷，每卷 fixture 里 3 题
    assert len(idx['records']) == 6
    assert idx['meta']['pages'] == 2
    assert idx['meta']['records'] == 6
    assert idx['meta']['parser_version'] == index_mod.PARSER_VERSION


def test_load_reuses_cache_without_network(stub_network, monkeypatch):
    index_mod.refresh()

    def boom():
        raise AssertionError('不应再次联网')

    monkeypatch.setattr(index_mod.site_io, 'list_papers', boom)
    idx = index_mod.load()
    assert len(idx['records']) == 6
    assert idx['meta']['stale'] is False


def _age_cache(days=8):
    data = json.loads(index_mod.CACHE_PATH.read_text(encoding='utf-8'))
    data['meta']['built_at'] -= days * 86400
    index_mod.CACHE_PATH.write_text(json.dumps(data), encoding='utf-8')


def test_ttl_expired_cache_is_flagged(stub_network):
    index_mod.refresh()
    _age_cache()
    assert index_mod.load(auto_refresh=False)['meta']['stale'] is True


def test_ttl_expired_triggers_rebuild(stub_network, monkeypatch):
    index_mod.refresh()
    _age_cache()
    calls = []
    real_build = index_mod.build
    monkeypatch.setattr(index_mod, 'build', lambda: calls.append(1) or real_build())
    idx = index_mod.load()
    assert calls == [1]
    assert idx['meta']['stale'] is False


def test_rebuild_failure_degrades_to_old_cache(stub_network, monkeypatch):
    index_mod.refresh()
    _age_cache()
    monkeypatch.setattr(index_mod.site_io, 'list_papers', lambda: [])
    idx = index_mod.load()
    assert idx['meta']['degraded'] is True
    assert len(idx['records']) == 6


def test_zero_item_page_aborts_and_keeps_old_cache(stub_network, monkeypatch):
    index_mod.refresh()
    before = index_mod.CACHE_PATH.read_bytes()
    monkeypatch.setattr(index_mod.site_io, 'fetch', lambda url: '<html>无题目</html>')
    with pytest.raises(index_mod.BuildError):
        index_mod.refresh()
    assert index_mod.CACHE_PATH.read_bytes() == before


def test_count_drift_over_20_percent_aborts(stub_network, monkeypatch):
    index_mod.refresh()
    before = index_mod.CACHE_PATH.read_bytes()
    # 单页自身题量与声明一致（不触发逐卷校验），但总页数减半导致总量漂移 50%
    monkeypatch.setattr(index_mod.site_io, 'list_papers', lambda: _papers(1))
    with pytest.raises(index_mod.BuildError) as exc:
        index_mod.refresh()
    assert '20' in str(exc.value)
    assert index_mod.CACHE_PATH.read_bytes() == before


def test_declared_count_mismatch_aborts(stub_network, monkeypatch):
    """matrix 声明每题量与解析结果不符即判定结构变化，旧缓存保留。"""
    index_mod.refresh()
    before = index_mod.CACHE_PATH.read_bytes()
    monkeypatch.setattr(index_mod.site_io, 'list_papers', lambda: _papers(2, declared=9))
    with pytest.raises(index_mod.BuildError) as exc:
        index_mod.refresh()
    assert '声明 9' in str(exc.value)
    assert index_mod.CACHE_PATH.read_bytes() == before


def test_fetch_failure_aborts_and_names_url(stub_network, monkeypatch):
    index_mod.refresh()
    before = index_mod.CACHE_PATH.read_bytes()

    def flaky(url):
        if url.endswith('p1'):
            raise FetchError(url, 'timed out')
        return FIXTURE

    monkeypatch.setattr(index_mod.site_io, 'fetch', flaky)
    with pytest.raises(index_mod.BuildError) as exc:
        index_mod.refresh()
    assert 'p1' in str(exc.value)
    assert index_mod.CACHE_PATH.read_bytes() == before


def test_atomic_write_leaves_no_temp(stub_network):
    index_mod.refresh()
    assert list(pathlib.Path(index_mod.CACHE_DIR).glob('*.tmp')) == []


def test_parser_version_change_invalidates(stub_network, monkeypatch):
    index_mod.refresh()
    data = json.loads(index_mod.CACHE_PATH.read_text(encoding='utf-8'))
    data['meta']['parser_version'] = '0'
    index_mod.CACHE_PATH.write_text(json.dumps(data), encoding='utf-8')
    calls = []
    monkeypatch.setattr(index_mod.site_io, 'list_papers',
                        lambda: calls.append(1) or _papers())
    assert index_mod.load()['meta']['parser_version'] == index_mod.PARSER_VERSION
    assert calls == [1]


def test_cache_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv('KAOYAN_MATRIX_CACHE', str(tmp_path / 'other.json'))
    assert index_mod.cache_path().name == 'other.json'


def test_records_carry_norm_and_hay(stub_network):
    idx = index_mod.refresh()
    assert all(r['norm'] and r['hay'] for r in idx['records'])
