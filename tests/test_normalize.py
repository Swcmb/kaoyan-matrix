# SPDX-License-Identifier: GPL-3.0-or-later
"""归一化层测试：同义写法必须折叠成同一字符串。"""
import pathlib

import pytest

from normalize import normalize


def test_greek_macro_equals_unicode():
    assert normalize("$\\lambda$") == normalize("λ")


def test_displaystyle_and_mathrm_stripped():
    latex = r"\displaystyle\int_{0}^{x} \mathrm{e}^{\cos t}\,\mathrm{d}t"
    # 手写的等价写法：下标 ₀ 与修饰字母 ˣ 由 NFKC 折叠成 0 与 x
    assert normalize(latex) == normalize("∫₀ˣ e^{cos t} dt") == "∫0xecostdt"


def test_frac_expanded():
    # \frac{1}{2} 展开成 1/2，再按标点剥离规则统一成 12
    assert normalize(r"$\frac{1}{2}$") == normalize("12")
    # 嵌套 frac 也必须能展开，不允许残留命令名
    out = normalize(r"\frac{\frac{a}{b}}{c}")
    assert "frac" not in out


def test_fullwidth_halfwidth_equal():
    assert normalize("ｆ（ｘ）") == normalize("f(x)")


@pytest.mark.parametrize(
    "junk", ["$", "{", "}", "\\", "^", "_", "(", ")", "[", "]", ",", "。", "，", " ", "\t"]
)
def test_punctuation_and_whitespace_dropped(junk):
    assert junk not in normalize(f"a{junk}b")


def test_relations_mapped():
    assert normalize(r"\leq") == normalize("≤")
    assert normalize(r"\rightarrow") == normalize("→")
    assert normalize(r"\infty") == normalize("∞")


def test_unknown_macro_leaves_no_command_name():
    assert "zzzunknown" not in normalize(r"\zzzunknown")


def test_lowercase_fold():
    assert normalize("X") == normalize("x")


def test_latex_form_matches_plain_form_selfauthored():
    """自造文本：LaTeX 写法与手打纯文本必须归一化到同一串。

    不用站点真题做断言——测试文件不保存题干原文；真实题干的等价性由下面
    那条幂等性测试在运行时用索引验证。
    """
    latex = r"曲线 $y=\sin x$ 在点 $(0,0)$ 处的切线斜率为 $\frac{1}{2}$"
    hand = "曲线 y=sinx 在点 (0,0) 处的切线斜率为 12"
    assert normalize(latex) == normalize(hand)


def test_normalize_is_idempotent_on_selfauthored_text():
    assert normalize(normalize(r"$\alpha+\beta=\gamma$")) == normalize(r"\alpha\beta\gamma")


@pytest.mark.skipif(not (pathlib.Path(__file__).resolve().parent.parent
                         / '.cache' / 'index.json').exists(),
                    reason='需要先构建索引')
def test_plain_rewriting_of_real_stems_is_equivalent():
    """手打形态能命中原文的根因：把行内公式就地归一化后整体再归一化，结果不变。

    题干运行时从索引读取，本文件不保存任何站点原文。
    """
    import re
    import index
    span = re.compile(r'\$[^$]*\$')
    records = index.load(auto_refresh=False)['records']
    checked = 0
    for r in records:
        if not r['stem'] or '  ' in r['stem']:
            continue
        plain = span.sub(lambda m: normalize(m.group(0)), r['stem'])
        assert normalize(plain) == normalize(r['stem']), r['detail_url']
        checked += 1
        if checked >= 200:
            break
    assert checked == 200
