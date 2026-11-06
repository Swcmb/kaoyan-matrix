# SPDX-License-Identifier: GPL-3.0-or-later
"""试卷页解析测试。fixture 为手写骨架，覆盖三种题型的标记差异。"""
import pathlib

import pytest

from parser import parse_paper

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "synthetic_paper.html"


@pytest.fixture(scope="module")
def html():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def items(html):
    return parse_paper(html, subject="模拟一", year=2099)


def test_three_items_parsed(items):
    assert len(items) == 3
    assert [it["num"] for it in items] == [1, 2, 3]


def test_type_and_score_fields(items):
    assert items[0]["type"] == "选择题" and items[0]["score"] == "5分"
    assert items[1]["type"] == "填空题"
    assert items[2]["type"] == "解答题" and items[2]["score"] == "12分"


def test_stem_only_covered(items):
    """`.stem` 与 `.stem.stem-only` 两种标记都必须解析出来——这是 10→22 那个坑的回归测试。"""
    assert all(it["stem"] for it in items)
    assert "切线斜率" in items[1]["stem"]
    assert "二重积分" in items[2]["stem"]


def test_tags_and_entities_stripped(items):
    for it in items:
        assert "&lt;" not in it["stem"] and "&gt;" not in it["stem"]
        assert "&nbsp;" not in it["stem"]
        assert "<p>" not in it["stem"] and "<div" not in it["stem"]
    # 实体必须反转义成真正的文本字符，这里出现的 < > 是内容而非标签
    assert "<结论>" in items[2]["stem"]


def test_detail_url_absolute(items):
    assert items[0]["detail_url"] == "https://mathabc.xyz/kaoyan/problem/9001/"
    assert items[2]["detail_url"].endswith("/9003/")


def test_options_only_for_choice_items(items):
    assert items[0]["options"] == ["A $f(x)$ 为奇函数", "B $f(x)$ 为偶函数"]
    assert items[1]["options"] == []
    assert items[2]["options"] == []


def test_norm_and_hay_prefilled(items):
    from normalize import normalize
    assert items[0]["norm"] == normalize(items[0]["stem"])
    # hay 含选项文本，保证用户连选项一起粘贴时仍能精确命中
    assert normalize("偶函数") in items[0]["hay"]
    assert normalize("偶函数") not in items[0]["norm"]


def test_subject_and_year_carried(items):
    assert all(it["subject"] == "模拟一" and it["year"] == 2099 for it in items)


def test_empty_html_returns_empty():
    assert parse_paper("", subject="x", year=1) == []


def test_latex_kept_verbatim_in_stem(items):
    """stem 保留原始 LaTeX，供展示；归一化只发生在 norm/hay。"""
    assert "x^{2}+1" in items[0]["stem"]
    assert "\\iint_{D}" in items[2]["stem"]
