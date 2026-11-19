"""Offline monotonic alignment suggestions; no semantic translation claims."""
import math
import re
from difflib import SequenceMatcher


def flat_slots(prs):
    slots = []
    for slide_n, slide in enumerate(prs.slides, 1):
        for shape in sorted(slide.shapes, key=lambda s: (s.top, s.left)):
            if shape.has_table:
                for ri, row in enumerate(shape.table.rows, 1):
                    for ci, cell in enumerate(row.cells, 1):
                        if cell.is_spanned:
                            continue
                        slots.append(dict(slide=slide_n, shape_id=shape.shape_id, row=ri, col=ci,
                                          kind='table_cell', text=cell.text, top=shape.top))
            elif shape.has_text_frame and shape.text.strip():
                slots.append(dict(slide=slide_n, shape_id=shape.shape_id, row='', col='',
                                  kind='text', text=shape.text, top=shape.top))
    return slots


def number_tokens(value):
    return set(re.findall(r'(?<!\w)\d+(?:[.,]\d+)*%?(?!\w)', value or ''))


def compatibility(block, slot, source_pos, target_pos):
    if (block['html_type'] == 'table_cell') != (slot['kind'] == 'table_cell'):
        return -1e6
    a = ' '.join(block['translation'].split()).casefold()
    b = ' '.join(slot['text'].split()).casefold()
    nums_a, nums_b = number_tokens(a), number_tokens(b)
    shared = len(nums_a & nums_b)
    missing = len(nums_a ^ nums_b)
    exact = SequenceMatcher(None, a, b).ratio()
    length_gap = abs(math.log((len(a) + 8) / (len(b) + 8)))
    loc_gap = abs(source_pos - target_pos)
    score = 1.3 - min(length_gap, 2.0) * .55 - loc_gap * 1.65
    score += shared * .85 - missing * .22
    if exact > .75:
        score += 1.2 * exact
    if block['html_type'].startswith('h') and block['html_type'][1:].isdigit():
        score += .15 if len(b) < 160 else -.3
    if not a or not b:
        score -= 1
    return score


def suggest(blocks, slots):
    """Global order alignment with skips. Suggestions never imply automatic approval."""
    n, m = len(blocks), len(slots)
    if not n or not m:
        return {}
    if n * m > 4_000_000:
        raise ValueError('Eşleştirme çok büyük (4 milyon üzeri aday). Dosyaları bölün.')
    # DP with gap penalty for missing/extra HTML or slide slots.
    prev = [j * -.65 for j in range(m + 1)]
    moves = bytearray((n + 1) * (m + 1))
    for i, block in enumerate(blocks, 1):
        cur = [i * -.65] + [0.] * m
        moves[i * (m + 1)] = 1
        for j, slot in enumerate(slots, 1):
            score = compatibility(block, slot, (i - .5) / n, (j - .5) / m)
            diag = prev[j - 1] + score
            up = prev[j] - .65
            left = cur[j - 1] - .65
            if diag >= up and diag >= left:
                cur[j] = diag; moves[i * (m + 1) + j] = 3
            elif up >= left:
                cur[j] = up; moves[i * (m + 1) + j] = 1
            else:
                cur[j] = left; moves[i * (m + 1) + j] = 2
        prev = cur
    i, j = n, m
    matches = {}
    while i and j:
        direction = moves[i * (m + 1) + j]
        if direction == 3:
            block, slot = blocks[i-1], slots[j-1]
            score = compatibility(block, slot, (i-.5)/n, (j-.5)/m)
            if score > 0:
                # Confidence labels are heuristic, not statistical probabilities.
                shared_nums = len(number_tokens(block['translation']) & number_tokens(slot['text']))
                exact = SequenceMatcher(None,block['translation'].casefold(),slot['text'].casefold()).ratio()
                if (exact > .88 and score > 2.0) or (shared_nums >= 2 and score >= 2.1):
                    confidence = 'yuksek'
                elif score >= 1.1:
                    confidence = 'orta'
                else:
                    confidence = 'dusuk'
                matches[i-1] = (slot, confidence, round(score, 2))
            i -= 1; j -= 1
        elif direction == 1:
            i -= 1
        else:
            j -= 1
    return matches
