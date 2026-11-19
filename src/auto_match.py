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
    # For large inputs, follow a corridor around the proportional ordering.
    # The minimum width lets neighboring rows overlap even with uneven lengths.
    radius = m if n * m <= 4_000_000 else max(64, (m + n - 1) // n)
    negative_infinity = float('-inf')
    previous_start = 0
    previous = [j * -.65 for j in range(min(m, radius) + 1)]
    moves = [(0, bytearray())]

    for i, block in enumerate(blocks, 1):
        center = i * m // n
        start = max(0, center - radius)
        end = min(m, center + radius)
        current = [negative_infinity] * (end - start + 1)
        directions = bytearray(len(current))
        if start == 0:
            current[0] = i * -.65
            directions[0] = 1

        for j in range(max(1, start), end + 1):
            index = j - start
            previous_index = j - previous_start
            diag = negative_infinity
            if 0 <= previous_index - 1 < len(previous):
                score = compatibility(block, slots[j - 1], (i - .5) / n, (j - .5) / m)
                diag = previous[previous_index - 1] + score
            up = previous[previous_index] - .65 if 0 <= previous_index < len(previous) else negative_infinity
            left = current[index - 1] - .65 if index else negative_infinity
            if diag >= up and diag >= left:
                current[index], directions[index] = diag, 3
            elif up >= left:
                current[index], directions[index] = up, 1
            else:
                current[index], directions[index] = left, 2

        moves.append((start, directions))
        previous_start, previous = start, current

    i, j = n, m
    matches = {}
    while i and j:
        start, directions = moves[i]
        direction = directions[j - start]
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
