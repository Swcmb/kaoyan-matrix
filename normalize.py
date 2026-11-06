# SPDX-License-Identifier: GPL-3.0-or-later
"""题干归一化：把带 LaTeX 的原文与手打的纯文本折叠成同一个可比字符串。

站点题干形如 ``$\\displaystyle\\int_{0}^{x} \\mathrm{e}^{\\cos t} \\mathrm{~d} t$``，
用户手打形如 ``∫₀ˣ e^cos t dt``。不做命令映射时两者匹配分会退化到与错误候选不可分，
因此这一层是整个工具的成败关键。
"""
import re
import unicodedata

__all__ = ["normalize", "MACROS", "KEEP_SYMBOLS"]

# LaTeX 命令 → Unicode/空。值为 '' 的是纯装饰命令，直接消失。
MACROS = {
    # 装饰与排版
    'displaystyle': '', 'textstyle': '', 'scriptstyle': '', 'limits': '', 'nolimits': '',
    'mathrm': '', 'mathbf': '', 'mathit': '', 'mathsf': '', 'mathtt': '', 'boldsymbol': '',
    'mbox': '', 'text': '', 'textrm': '', 'textbf': '', 'operatorname': '',
    'left': '', 'right': '', 'big': '', 'Big': '', 'bigg': '', 'Bigg': '',
    'bigl': '', 'bigr': '', 'Bigl': '', 'Bigr': '', 'leftarrow': '←',
    'quad': '', 'qquad': '', 'hspace': '', 'hfill': '', 'small': '',
    # 环境声明
    'begin': '', 'end': '', 'array': '', 'cases': '', 'aligned': '', 'align': '',
    'matrix': '', 'pmatrix': '', 'bmatrix': '', 'vmatrix': '', 'Vmatrix': '',
    'arraystretch': '', 'nonumber': '',
    # 关系与运算
    'leq': '≤', 'le': '≤', 'geq': '≥', 'ge': '≥', 'neq': '≠', 'ne': '≠',
    'approx': '≈', 'equiv': '≡', 'propto': '∝', 'sim': '∼', 'simeq': '≃',
    'll': '≪', 'gg': '≫', 'to': '→', 'rightarrow': '→', 'longrightarrow': '→',
    'Rightarrow': '⇒', 'implies': '⇒', 'iff': '⇔', 'parallel': '∥', 'perp': '⊥',
    'cdot': '', 'times': '×', 'div': '÷', 'pm': '±', 'mp': '∓', 'ast': '*',
    'circ': '∘', 'bullet': '', 'star': '★', 'diamond': '◇', 'wedge': '∧',
    'vee': '∨', 'neg': '¬', 'land': '∧', 'lor': '∨',
    # 集合与逻辑
    'in': '∈', 'notin': '∉', 'ni': '∋', 'subset': '⊂', 'subseteq': '⊆',
    'supset': '⊃', 'supseteq': '⊇', 'cup': '∪', 'cap': '∩',
    'emptyset': '∅', 'varnothing': '∅', 'forall': '∀', 'exists': '∃',
    'nexists': '∄', 'setminus': '',
    # 算子与大符号
    'int': '∫', 'iint': '∬', 'iiint': '∭', 'oint': '∮',
    'sum': '∑', 'prod': '∏', 'sqrt': '√', 'partial': '∂', 'nabla': '∇',
    'infty': '∞', 'infinity': '∞', 'ell': 'ℓ', 'hbar': 'ℏ',
    # 点与省略号
    'ldots': '…', 'cdots': '⋯', 'dots': '…', 'vdots': '⋮', 'ddots': '⋱', 'trdots': '…',
    # 上下箭头与差异
    'uparrow': '↑', 'downarrow': '↓', 'triangle': '△', 'square': '□',
    'degree': '°', 'prime': '′',
    # 希腊字母（小写）
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε',
    'varepsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ', 'vartheta': 'ϑ',
    'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'xi': 'ξ', 'omicron': 'ο',
    'pi': 'π', 'varpi': 'ϖ', 'rho': 'ρ', 'varrho': 'ϱ', 'sigma': 'σ',
    'varsigma': 'ς', 'tau': 'τ', 'upsilon': 'υ', 'phi': 'φ', 'varphi': 'φ',
    'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    # 希腊字母（大写）
    'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ',
    'Pi': 'Π', 'Sigma': 'Σ', 'Upsilon': 'Υ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
    # 函数名：保留字面，避免被当成未知命令整段丢弃
    'lim': 'lim', 'limsup': 'limsup', 'liminf': 'liminf', 'max': 'max', 'min': 'min',
    'sup': 'sup', 'inf': 'inf', 'sin': 'sin', 'cos': 'cos', 'tan': 'tan',
    'cot': 'cot', 'sec': 'sec', 'csc': 'csc', 'arcsin': 'arcsin', 'arccos': 'arccos',
    'arctan': 'arctan', 'sinh': 'sinh', 'cosh': 'cosh', 'tanh': 'tanh',
    'coth': 'coth', 'ln': 'ln', 'lg': 'lg', 'log': 'log', 'exp': 'exp',
    'det': 'det', 'dim': 'dim', 'gcd': 'gcd', 'tr': 'tr', 'trace': 'trace',
    'rank': 'rank', 'diag': 'diag', 'adj': 'adj', 'sgn': 'sgn',
    'mod': 'mod', 'pmod': 'mod', 'bmod': 'mod',
    # 重音与向量记号：只丢装饰，保留内容
    'hat': '', 'bar': '', 'vec': '', 'tilde': '', 'dot': '', 'ddot': '',
    'overline': '', 'underline': '', 'widehat': '', 'widetilde': '', 'check': '',
    # 括号与分数由结构规则先行处理，这里兜底
    'frac': '', 'dfrac': '', 'tfrac': '', 'binom': '', 'choose': '',
    'atop': '', 'over': '', 'above': '', 'below': '',
    'parbox': '', 'raisebox': '', 'color': '', 'textcolor': '',
}

# 归一化后仍保留的非字母数字符号：只允许映射表产出过的那些。
KEEP_SYMBOLS = set(
    "≤≥≠≈≡∝∼≃≪≫→←⇒⇔∥⊥×÷±∓*∘∧∨¬∈∉∋⊂⊆⊃⊇∪∩∅∀∃∄"
    "∫∬∭∮∑∏√∂∇∞ℓℏ…⋯⋮⋱↑↓△□°′★◇"
)

# 预编译：命令、\frac 结构、环境声明
_RE_FRAC = re.compile(r'\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}')
_RE_ENV = re.compile(r'\\(?:begin|end)\s*\{[^{}]*\}')
_RE_MACRO = re.compile(r'\\([a-zA-Z]+)\*?')
_RE_BACKSLASH = re.compile(r'\\+')


def _expand_frac(text: str) -> str:
    """迭代展开 \\frac{a}{b} → (a)/(b)，嵌套一次调用即可全部剥掉。"""
    for _ in range(6):
        new = _RE_FRAC.sub(r'(\1)/(\2)', text)
        if new == text:
            break
        text = new
    # 残留的 \frac 命令名交给后面的映射表
    return text


def normalize(text: str) -> str:
    t = unicodedata.normalize('NFKC', text or '')
    t = _expand_frac(t)
    t = _RE_ENV.sub('', t)
    t = _RE_MACRO.sub(lambda m: MACROS.get(m.group(1), ''), t)
    t = _RE_BACKSLASH.sub('', t)
    t = t.replace('{', '').replace('}', '')
    kept = [ch for ch in t if ch.isalnum() or ch in KEEP_SYMBOLS]
    return ''.join(kept).lower()
