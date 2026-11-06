# SPDX-License-Identifier: GPL-3.0-or-later
"""试卷页 → 结构化题目。纯函数，不碰网络。

站点 DOM 约定（2026-11-06 实测）：
  ``.problem-list`` > ``.problem-item`` > ``.num-badge``「第N题 · 题型 · 分值」
  题干在 ``.stem``（选择题）或 ``.stem.stem-only``（填空/解答题），
  选择题另带若干 ``.choice-text``，末尾一个 ``.view-detail-link``。
"""
import re

from normalize import normalize

__all__ = ["parse_paper", "strip_tags", "BASE"]

BASE = "https://mathabc.xyz"

_RE_ITEM = re.compile(r'<div class="problem-item">')
_RE_BADGE = re.compile(r'class="num-badge">\s*([^<]*?)\s*<')
_RE_STEM = re.compile(r'<div class="stem[^"]*">(.*?)</div>', re.S)
_RE_DETAIL = re.compile(r'href="(/kaoyan/problem/\d+/)"')
_RE_CARD = re.compile(r'<div class="choice-card">')
_RE_LABEL = re.compile(r'class="choice-label">\s*(.*?)\s*</span>', re.S)
_RE_TEXT = re.compile(r'class="choice-text">(.*?)</span>', re.S)
_RE_TAG = re.compile(r'<[^>]*>')
_RE_SPACE = re.compile(r'\s+')

_ENTITIES = (
    ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'"),
    ('&nbsp;', ' '), ('&rsaquo;', '›'), ('&amp;', '&'),
)


def strip_tags(html: str) -> str:
    """去标签 → 反转义实体 → 折叠空白。顺序不可调换：
    先剥标签才能把 ``&lt;`` 当文本处理，先折叠空白会把 ``&nbsp;`` 漏成多余空格。
    """
    text = _RE_TAG.sub(' ', html or '')
    for src, dst in _ENTITIES:
        text = text.replace(src, dst)
    return _RE_SPACE.sub(' ', text).strip()


def _parse_badge(badge: str) -> tuple[int, str, str]:
    parts = [p.strip() for p in badge.split('·')]
    num = int(re.sub(r'\D', '', parts[0]) or 0) if parts else 0
    return num, (parts[1] if len(parts) > 1 else ''), (parts[2] if len(parts) > 2 else '')


def _parse_options(block: str) -> list[str]:
    """按 choice-card 切块，标号与文本成对出现，输出形如 ``A $f(x)$ 为奇函数``。

    站点用 ``<span class="choice-label">`` 与 ``<span class="choice-text">``；
    逐卡切分比全局配对稳，缺标签的卡片不会串到下一张卡。
    """
    starts = [m.start() for m in _RE_CARD.finditer(block)]
    options = []
    for i, start in enumerate(starts):
        card = block[start:starts[i + 1] if i + 1 < len(starts) else len(block)]
        label, text = _RE_LABEL.search(card), _RE_TEXT.search(card)
        if not text:
            continue
        options.append(' '.join(p for p in (
            strip_tags(label.group(1)) if label else '', strip_tags(text.group(1))) if p))
    return options


def parse_paper(html: str, subject: str, year: int) -> list[dict]:
    if not html:
        return []
    starts = [m.start() for m in _RE_ITEM.finditer(html)]
    records = []
    for i, start in enumerate(starts):
        block = html[start:starts[i + 1] if i + 1 < len(starts) else len(html)]
        badge, stem = _RE_BADGE.search(block), _RE_STEM.search(block)
        if not badge or not stem:
            continue
        num, qtype, score = _parse_badge(badge.group(1))
        stem_text = strip_tags(stem.group(1))
        options = _parse_options(block)
        detail = _RE_DETAIL.search(block)
        norm = normalize(stem_text)
        # hay 把选项一并纳入匹配面：用户常连 A/B/C/D 一起粘贴
        hay = normalize(stem_text + ' ' + ' '.join(options))
        records.append({
            'subject': subject,
            'year': year,
            'num': num,
            'type': qtype,
            'score': score,
            'stem': stem_text,
            'options': options,
            'detail_url': BASE + detail.group(1) if detail else '',
            'norm': norm,
            'hay': hay,
        })
    return records
