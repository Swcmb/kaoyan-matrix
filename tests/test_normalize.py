# SPDX-License-Identifier: GPL-3.0-or-later
"""归一化层测试：同义写法必须折叠成同一字符串。"""
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


def test_real_stem_matches_plain_rewriting():
    """站点原文题干（带 LaTeX）与手打无公式版本必须归一化到同一前缀。"""
    site = r"设随机变量 $\mathrm{X}, \mathrm{Y}$ 相互独立，且均服从参数为 $\lambda$ 的指数分布"
    hand = "设随机变量 X, Y 相互独立，且均服从参数为 λ 的指数分布"
    assert normalize(site) == normalize(hand)
