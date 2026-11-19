"""Select one-to-one bilingual matches from local semantic vectors."""

from collections import Counter, defaultdict
import re
import unicodedata

import numpy as np


TEXT_SIMILARITY = 0.84
SHORT_SIMILARITY = 0.92
TEXT_MARGIN = 0.08
TABLE_MARGIN = 0.06

NUMBER = re.compile(r"%?\s*[-−+]?\d+(?:[.,]\d+)*(?:\s*%)?")
WORD = re.compile(r"[^\W\d_]+")
YEAR = re.compile(r"(?:19|20)\d{2}")


def _canonical(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _line_count(text):
    return sum(bool(line.strip()) for line in text.splitlines())


def _numbers(text):
    # Retain quantity order while allowing a single year to move around a
    # single quantity, a common difference between English and Turkish syntax.
    numbers = tuple(
        (
            re.sub(r"[.,]", ".", re.sub(r"[%\s]", "", token).replace("−", "-")),
            "%" in token,
        )
        for token in NUMBER.findall(text)
    )
    if len(numbers) == 2 and sum(
        not percent and YEAR.fullmatch(number) is not None for number, percent in numbers
    ) == 1:
        return tuple(sorted(numbers))
    return numbers


def _unit_vectors(vectors, size):
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) != size or not np.isfinite(vectors).all():
        raise ValueError("Metin vektörleri eksik veya geçersiz.")
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(lengths > 0, lengths, 1)


def _nearest(left, right):
    """Find best matches and score gaps without retaining a full score matrix."""
    indices = np.empty(len(left), dtype=np.intp)
    scores = np.empty(len(left), dtype=np.float32)
    margins = np.empty(len(left), dtype=np.float32)
    batch_size = max(1, 500_000 // len(right))
    for first in range(0, len(left), batch_size):
        matrix = left[first:first + batch_size] @ right.T
        rows = np.arange(len(matrix))
        best = matrix.argmax(axis=1)
        best_scores = matrix[rows, best]
        matrix[rows, best] = -np.inf
        result = slice(first, first + len(matrix))
        indices[result] = best
        scores[result] = best_scores
        margins[result] = best_scores - matrix.max(axis=1)
    return indices, scores, margins


def _text_matches(source, target, source_text, target_text, source_vectors, target_vectors):
    if not source or not target:
        return {}

    source_counts = Counter(source_text[i] for i in source)
    target_counts = Counter(target_text[j] for j in target)
    exact_targets = {target_text[j]: j for j in target if target_counts[target_text[j]] == 1}
    matches = {
        i: (exact_targets[source_text[i]], 1.0)
        for i in source
        if source_text[i] and source_counts[source_text[i]] == 1 and source_text[i] in exact_targets
    }

    target_claims = {j for j, _ in matches.values()}
    source_subset, target_subset = source_vectors[source], target_vectors[target]
    best, scores, gaps = _nearest(source_subset, target_subset)
    reverse, _, reverse_gaps = _nearest(target_subset, source_subset)
    for index, i in enumerate(source):
        target_index = best[index]
        j = target[target_index]
        if i in matches or j in target_claims or reverse[target_index] != index:
            continue
        if min(gaps[index], reverse_gaps[target_index]) < TEXT_MARGIN:
            continue

        left, right = source_text[i], target_text[j]
        left_words, right_words = WORD.findall(left), WORD.findall(right)
        if not left_words or not right_words or _numbers(left) != _numbers(right):
            continue
        threshold = SHORT_SIMILARITY if min(len(left_words), len(right_words)) == 1 else TEXT_SIMILARITY
        if scores[index] >= threshold:
            matches[i] = (j, float(scores[index]))
    return matches


def _table_groups(blocks, slots, target_text):
    source_tables = defaultdict(dict)
    dimensions = {}
    for i, block in enumerate(blocks):
        table = block.get("source_table")
        if table is not None and table != "" and block.get("source_rows") and block.get("source_cols"):
            source_tables[table][block["source_row"], block["source_col"]] = i
            dimensions[table] = (block["source_rows"], block["source_cols"])

    target_tables = defaultdict(dict)
    for j, slot in enumerate(slots):
        if slot["kind"] == "table_cell":
            target_tables[slot["slide"], slot["shape_id"]][slot["row"], slot["col"]] = j

    # Equal dimensions and occupied coordinates are required. Spanned PowerPoint
    # cells do not appear in the inventory, so incomplete grids are excluded.
    targets_by_layout = defaultdict(list)
    for cells in target_tables.values():
        rows = max(row for row, _ in cells)
        cols = max(col for _, col in cells)
        if len(cells) == rows * cols:
            occupied = tuple(sorted(coord for coord, j in cells.items() if target_text[j]))
            targets_by_layout[(rows, cols, occupied)].append(cells)
    for table, cells in source_tables.items():
        occupied = tuple(sorted(cells))
        layout = (*dimensions[table], occupied)
        yield [cells[coord] for coord in occupied], (
            [target[coord] for coord in occupied] for target in targets_by_layout[layout]
        )


def _table_score(left, right, scores):
    """Use corresponding cells as evidence for a whole-table match."""
    evidence = []
    for source, target, score in zip(left, right, scores):
        source_numbers, target_numbers = _numbers(source), _numbers(target)
        if source_numbers != target_numbers:
            return None
        source_words, target_words = WORD.findall(source), WORD.findall(target)
        if source == target:
            if source_words:
                evidence.append(1.0)
            continue
        if not source_words and not target_words and source_numbers:
            continue
        if not source_words or not target_words or score < 0.74:
            return None
        evidence.append(float(score))
    if len(evidence) < 2:
        return None
    return sum(evidence) / len(evidence)


def _table_matches(blocks, slots, source_text, target_text, source_vectors, target_vectors):
    source_candidates = defaultdict(list)
    target_candidates = defaultdict(list)
    for source, targets in _table_groups(blocks, slots, target_text):
        left = [source_text[i] for i in source]
        for target in targets:
            right = [target_text[j] for j in target]
            similarities = np.einsum("ij,ij->i", source_vectors[source], target_vectors[target])
            score = _table_score(left, right, similarities)
            if score is not None:
                source_candidates[source[0]].append((score, target[0], source, target))
                target_candidates[target[0]].append((score, source[0]))

    matches = {}
    for source_id, candidates in source_candidates.items():
        ranked = sorted(candidates, reverse=True)
        score, target_id, source, target = ranked[0]
        reverse = sorted(target_candidates[target_id], reverse=True)
        if score < 0.87 or reverse[0][1] != source_id:
            continue
        if len(ranked) > 1 and score - ranked[1][0] < TABLE_MARGIN:
            continue
        if len(reverse) > 1 and score - reverse[1][0] < TABLE_MARGIN:
            continue
        matches.update({i: (j, score) for i, j in zip(source, target)})
    return matches


def suggest_automatic(blocks, slots, source_vectors, target_vectors):
    """Return accepted source indices and their unique PowerPoint targets."""
    if not blocks or not slots:
        return {}
    source_text = [_canonical(block["translation"]) for block in blocks]
    target_text = [_canonical(slot["text"]) for slot in slots]
    source_vectors = _unit_vectors(source_vectors, len(blocks))
    target_vectors = _unit_vectors(target_vectors, len(slots))
    if source_vectors.shape[1] != target_vectors.shape[1]:
        raise ValueError("Metin vektörü boyutları uyuşmuyor.")

    source = [i for i, block in enumerate(blocks) if block["html_type"] != "table_cell" and source_text[i]]
    target = [j for j, slot in enumerate(slots) if slot["kind"] == "text" and target_text[j]]
    matches = _text_matches(source, target, source_text, target_text, source_vectors, target_vectors)
    # A single HTML paragraph can describe only part of a multiline shape.
    matches = {
        i: (j, score) for i, (j, score) in matches.items()
        if _line_count(blocks[i]["translation"]) >= _line_count(slots[j]["text"])
    }
    matches.update(_table_matches(blocks, slots, source_text, target_text, source_vectors, target_vectors))
    return {i: (slots[j], "otomatik", round(score, 3)) for i, (j, score) in matches.items()}
