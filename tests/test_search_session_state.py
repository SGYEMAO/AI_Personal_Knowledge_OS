"""Tests for preserving Search UI state across Streamlit reruns."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import (
    _ensure_search_session_state,
    _open_file_from_button,
    _result_button_key,
    _store_keyword_search_results,
    _store_semantic_search_results,
)


class SearchSessionStateTests(unittest.TestCase):
    """Verify Search results survive file-open button interactions."""

    def test_keyword_search_results_can_be_saved_in_session_state(self) -> None:
        """Keyword results are retained for later rerenders."""
        state: dict = {}
        results = [{"id": 1, "title": "Keyword Result"}]

        _store_keyword_search_results(results, state)

        self.assertTrue(state["last_keyword_search_ran"])
        self.assertEqual(state["last_search_results"], results)

    def test_semantic_search_results_can_be_saved_in_session_state(self) -> None:
        """Semantic results are retained for later rerenders."""
        state: dict = {}
        results = [{"id": "2", "title": "Semantic Result", "distance": 0.12}]

        _store_semantic_search_results(results, state)

        self.assertTrue(state["last_semantic_search_ran"])
        self.assertEqual(state["last_semantic_results"], results)

    def test_open_file_action_does_not_clear_cached_results(self) -> None:
        """Opening a local file records a message without clearing search results."""
        state: dict = {}
        keyword_results = [{"id": 1, "title": "Keyword Result"}]
        semantic_results = [{"id": "2", "title": "Semantic Result"}]
        _ensure_search_session_state(state)
        state["last_search_results"] = list(keyword_results)
        state["last_semantic_results"] = list(semantic_results)

        with patch("app.open_local_file", return_value=(True, "Opened successfully.")) as opener:
            success, message = _open_file_from_button(
                r"D:\CloudAdmin\test.pdf",
                "open_source_1",
                state,
            )

        self.assertTrue(success)
        self.assertEqual(message, "Opened successfully.")
        self.assertEqual(state["last_search_results"], keyword_results)
        self.assertEqual(state["last_semantic_results"], semantic_results)
        self.assertEqual(state["file_open_messages"]["open_source_1"], "Opened successfully.")
        opener.assert_called_once_with(r"D:\CloudAdmin\test.pdf")

    def test_open_file_button_keys_include_document_id(self) -> None:
        """Source and Markdown button keys use stable document ids."""
        result = {"id": 42, "title": "Local Note"}

        self.assertEqual(_result_button_key(result, "source"), "open_source_42")
        self.assertEqual(_result_button_key(result, "markdown"), "open_markdown_42")


if __name__ == "__main__":
    unittest.main()
