"""
GDIFSEA: Gaussian Distributed Independent Frequently Subsequence Extraction Algorithm.
Paper: independent support, frequent closed substrings, N-GRAM correlation graph.
No DBN or PB; pure string/graph operations.
"""
from collections import defaultdict
from typing import List, Set, Tuple


def build_ngram_graph(strings: List[str], max_len: int) -> dict:
    """
    Build N-GRAM correlation graph: vertices = substrings, edges = (parent, child) by length.
    Returns dict: substring -> { 'support': int, 'children': set of longer substrings }.
    """
    g: dict = defaultdict(lambda: {"support": 0, "children": set()})
    for s in strings:
        n = len(s)
        for length in range(1, min(max_len, n) + 1):
            for start in range(n - length + 1):
                sub = s[start : start + length]
                g[sub]["support"] += 1
                if length > 1:
                    p1 = s[start : start + length - 1]
                    p2 = s[start + 1 : start + length]
                    g[p1]["children"].add(sub)
                    g[p2]["children"].add(sub)
    return dict(g)


def independent_support(
    alpha: str, strings: List[str], frequent_closed: Set[str]
) -> int:
    """
    Independent support of substring α in S under limit F (frequent closed set).
    Count matches of α that are not contained in a longer frequent closed substring.
    """
    count = 0
    for s in strings:
        idx = 0
        while True:
            pos = s.find(alpha, idx)
            if pos == -1:
                break
            # Check independence: no γ in F with α ⊂ γ containing this occurrence
            independent = True
            for fc in frequent_closed:
                if len(fc) > len(alpha) and alpha in fc and s.find(fc, pos) == pos:
                    independent = False
                    break
            if independent:
                count += 1
            idx = pos + 1
    return count


def gdifsea(
    strings: List[str],
    support_threshold: int,
    max_substring_len: int = 20,
) -> List[Tuple[str, int]]:
    """
    GDIFSEA: return list of (frequent independent substring, independent support).
    Uses N-GRAM graph, filters by support threshold, then computes independent support.
    """
    g = build_ngram_graph(strings, max_substring_len)
    # Frequent closed substrings (simplified: support >= ξ, and no superstring has same support)
    by_len: defaultdict = defaultdict(list)
    for sub, data in g.items():
        if data["support"] >= support_threshold:
            by_len[len(sub)].append((sub, data["support"]))

    # Sort by length descending for independent support
    all_subs = sorted(g.keys(), key=lambda x: (-len(x), x))
    frequent_closed = set()
    for sub in all_subs:
        if g[sub]["support"] < support_threshold:
            continue
        # Closed: no proper superstring with same support
        closed = True
        for c in g[sub]["children"]:
            if g.get(c, {}).get("support") >= g[sub]["support"]:
                closed = False
                break
        if closed:
            frequent_closed.add(sub)

    result: List[Tuple[str, int]] = []
    for sub in all_subs:
        if g[sub]["support"] < support_threshold:
            continue
        ind_sup = independent_support(sub, strings, frequent_closed)
        if ind_sup >= support_threshold:
            result.append((sub, ind_sup))
    return result
