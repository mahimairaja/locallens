"""Tests for query arithmetic parser and vector combination."""

import math

import numpy as np
import pytest

from locallens.pipeline.query_parser import (
    ParsedQuery,
    QueryTerm,
    combine_query_vectors,
    parse_query,
)


class TestParseQuery:
    def test_simple_query(self):
        pq = parse_query("pricing strategy")
        assert len(pq.terms) == 2
        assert pq.is_arithmetic is False
        assert pq.base_text == "pricing strategy"

    def test_subtraction(self):
        pq = parse_query("climate change -demographics")
        assert len(pq.terms) == 3
        assert pq.is_arithmetic is True
        assert pq.terms[0].text == "climate"
        assert pq.terms[0].sign == 1.0
        assert pq.terms[2].text == "demographics"
        assert pq.terms[2].sign == -1.0
        assert pq.base_text == "climate change"

    def test_multiple_operators(self):
        pq = parse_query("pricing +recent -draft -internal")
        assert len(pq.terms) == 4
        assert pq.is_arithmetic is True
        assert pq.terms[0].sign == 1.0  # pricing
        assert pq.terms[1].sign == 1.0  # +recent
        assert pq.terms[2].sign == -1.0  # -draft
        assert pq.terms[3].sign == -1.0  # -internal

    def test_all_positive(self):
        pq = parse_query("+revenue +sales +growth")
        assert len(pq.terms) == 3
        assert pq.is_arithmetic is True
        assert all(t.sign == 1.0 for t in pq.terms)

    def test_quoted_terms(self):
        pq = parse_query('+"pricing strategy" -"internal draft"')
        assert len(pq.terms) == 2
        assert pq.terms[0].text == "pricing strategy"
        assert pq.terms[0].sign == 1.0
        assert pq.terms[1].text == "internal draft"
        assert pq.terms[1].sign == -1.0

    def test_cpp_not_split(self):
        """C++ should not be treated as C with a + operator."""
        pq = parse_query("C++ programming")
        # C++ is a single token, not split on the ++
        assert any(t.text == "C++" for t in pq.terms)

    def test_empty_query(self):
        pq = parse_query("")
        assert len(pq.terms) == 0
        assert pq.is_arithmetic is False
        assert pq.base_text == ""

    def test_whitespace_only(self):
        pq = parse_query("   ")
        assert len(pq.terms) == 0

    def test_no_operator_means_not_arithmetic(self):
        pq = parse_query("machine learning")
        assert pq.is_arithmetic is False

    def test_base_text_excludes_negatives(self):
        pq = parse_query("auth -test +web")
        assert pq.base_text == "auth web"

    def test_to_dict(self):
        pq = parse_query("auth -test +web")
        d = pq.to_dict()
        assert d == [
            {"text": "auth", "sign": "+"},
            {"text": "test", "sign": "-"},
            {"text": "web", "sign": "+"},
        ]


class TestCombineQueryVectors:
    @staticmethod
    def _mock_embed(text: str) -> list[float]:
        """Deterministic mock embedder: hash text to a fixed vector."""
        rng = np.random.RandomState(hash(text) % (2**31))
        vec = rng.randn(384)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

    def test_single_term_normalized(self):
        pq = ParsedQuery(
            terms=[QueryTerm(text="hello", sign=1.0)],
            is_arithmetic=False,
        )
        result = combine_query_vectors(pq, self._mock_embed)
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 1e-6

    def test_addition_changes_vector(self):
        pq_base = ParsedQuery(terms=[QueryTerm("hello", 1.0)])
        pq_plus = ParsedQuery(
            terms=[QueryTerm("hello", 1.0), QueryTerm("world", 1.0)],
            is_arithmetic=True,
        )
        v_base = combine_query_vectors(pq_base, self._mock_embed)
        v_plus = combine_query_vectors(pq_plus, self._mock_embed)
        assert v_base != v_plus

    def test_subtraction_changes_direction(self):
        pq_base = ParsedQuery(terms=[QueryTerm("hello", 1.0)])
        pq_minus = ParsedQuery(
            terms=[QueryTerm("hello", 1.0), QueryTerm("world", -1.0)],
            is_arithmetic=True,
        )
        v_base = combine_query_vectors(pq_base, self._mock_embed)
        v_minus = combine_query_vectors(pq_minus, self._mock_embed)
        assert v_base != v_minus

    def test_result_is_normalized(self):
        pq = ParsedQuery(
            terms=[
                QueryTerm("alpha", 1.0),
                QueryTerm("beta", 1.0),
                QueryTerm("gamma", -1.0),
            ],
            is_arithmetic=True,
        )
        result = combine_query_vectors(pq, self._mock_embed)
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 1e-6

    def test_empty_query_raises(self):
        pq = ParsedQuery(terms=[])
        with pytest.raises(ValueError, match="empty query"):
            combine_query_vectors(pq, self._mock_embed)

    def test_returns_list_of_float(self):
        pq = ParsedQuery(terms=[QueryTerm("test", 1.0)])
        result = combine_query_vectors(pq, self._mock_embed)
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)
