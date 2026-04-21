"""Query arithmetic parser for Semantra-inspired search refinement.

Parses queries with +/- operators into components that can be embedded
separately and combined via vector arithmetic before searching.

Examples::

    parse_query("pricing strategy")
    # -> ParsedQuery(terms=[QueryTerm("pricing strategy", +1)], is_arithmetic=False)

    parse_query("climate change -demographics +recent")
    # -> ParsedQuery(terms=[
    #      QueryTerm("climate change", +1),
    #      QueryTerm("demographics", -1),
    #      QueryTerm("recent", +1),
    #    ], is_arithmetic=True)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class QueryTerm:
    """A single component of a parsed query."""

    text: str
    sign: float  # +1.0 for add, -1.0 for subtract
    weight: float = 1.0


@dataclass
class ParsedQuery:
    """Result of parsing a query string with optional +/- operators."""

    terms: list[QueryTerm] = field(default_factory=list)
    is_arithmetic: bool = False

    @property
    def base_text(self) -> str:
        """Positive terms joined for BM25 keyword search."""
        return " ".join(t.text for t in self.terms if t.sign > 0)

    @property
    def full_text(self) -> str:
        """All terms joined (ignoring signs) for display."""
        return " ".join(t.text for t in self.terms)

    def to_dict(self) -> list[dict[str, str]]:
        """Serialize for API responses."""
        return [
            {"text": t.text, "sign": "+" if t.sign > 0 else "-"} for t in self.terms
        ]


# Match: an operator (+/-) followed by a quoted phrase or word, OR a
# standalone quoted phrase or word. The operator must be preceded by
# whitespace or string start to avoid splitting on C++ or hyphenated words.
_TOKEN_RE = re.compile(
    r'(?:(?<=\s)|^)([+-])\s*"([^"]+)"'  # op + "quoted phrase"
    r"|"
    r"(?:(?<=\s)|^)([+-])\s*(\S+)"  # op + word
    r"|"
    r'"([^"]+)"'  # standalone "quoted phrase"
    r"|"
    r"(\S+)",  # standalone word
)


def parse_query(raw: str) -> ParsedQuery:
    """Parse a query string with optional +/- arithmetic operators.

    Rules:
    - Text before any +/- operator is the base query (positive)
    - ``+term`` adds a concept to the search direction
    - ``-term`` subtracts a concept from the search direction
    - Quoted phrases: ``+"exact phrase"`` and ``-"another phrase"``
    - A query without operators returns ``is_arithmetic=False``
    """
    raw = raw.strip()
    if not raw:
        return ParsedQuery()

    terms: list[QueryTerm] = []
    has_operator = False

    for match in _TOKEN_RE.finditer(raw):
        # Groups: 1=op_quoted, 2=quoted_text, 3=op_word, 4=word_text,
        #         5=standalone_quoted, 6=standalone_word
        op_quoted, quoted_text = match.group(1), match.group(2)
        op_word, word_text = match.group(3), match.group(4)
        standalone_quoted = match.group(5)
        standalone_word = match.group(6)

        if op_quoted and quoted_text:
            sign = -1.0 if op_quoted == "-" else 1.0
            has_operator = True
            terms.append(QueryTerm(text=quoted_text.strip(), sign=sign, weight=1.0))
        elif op_word and word_text:
            sign = -1.0 if op_word == "-" else 1.0
            has_operator = True
            terms.append(QueryTerm(text=word_text.strip(), sign=sign, weight=1.0))
        elif standalone_quoted:
            terms.append(
                QueryTerm(text=standalone_quoted.strip(), sign=1.0, weight=1.0)
            )
        elif standalone_word:
            text = standalone_word.strip()
            if text:
                terms.append(QueryTerm(text=text, sign=1.0, weight=1.0))

    return ParsedQuery(terms=terms, is_arithmetic=has_operator)


def combine_query_vectors(
    parsed: ParsedQuery,
    embed_fn: Callable[[str], list[float]],
) -> list[float]:
    """Embed each query term and combine via vector arithmetic.

    For ``"pricing strategy -draft +recent"``:

    1. embed("pricing strategy") -> vec_a
    2. embed("draft") -> vec_b
    3. embed("recent") -> vec_c
    4. result = vec_a - vec_b + vec_c
    5. L2-normalize(result)

    Returns a ``list[float]`` compatible with ``store.search()``.
    """
    import numpy as np

    if not parsed.terms:
        raise ValueError("Cannot combine vectors for empty query")

    combined = None
    for term in parsed.terms:
        vec = np.array(embed_fn(term.text), dtype=np.float64)
        if combined is None:
            combined = np.zeros_like(vec)
        combined += term.sign * term.weight * vec

    assert combined is not None
    norm = np.linalg.norm(combined)
    if norm > 0:
        combined = combined / norm

    result: list[float] = combined.tolist()
    return result
