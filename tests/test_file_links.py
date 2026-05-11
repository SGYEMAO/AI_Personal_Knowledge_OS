"""Tests for opening local files from Search results."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from src.utils import open_local_file


class LocalFileLinkTests(unittest.TestCase):
    """Verify local file opener behavior for Streamlit buttons."""

    def test_missing_file_returns_false(self) -> None:
        """Missing files return a clean failure instead of raising."""
        success, message = open_local_file(r"D:\missing\test.pdf")

        self.assertFalse(success)
        self.assertEqual(message, "File not found.")

    def test_windows_path_calls_startfile(self) -> None:
        """Windows-style paths are passed to os.startfile after validation."""
        with patch("src.utils.Path") as mock_path_class, patch(
            "src.utils.os.startfile", create=True
        ) as mock_startfile:
            mock_path = mock_path_class.return_value.expanduser.return_value
            mock_path.exists.return_value = True
            mock_path.is_file.return_value = True
            mock_path.resolve.return_value = Path("D:/CloudAdmin/test.pdf")

            success, message = open_local_file(r"D:\CloudAdmin\test.pdf")

        self.assertTrue(success)
        self.assertEqual(message, "Opened successfully.")
        mock_path_class.assert_called_once_with(r"D:\CloudAdmin\test.pdf")
        mock_startfile.assert_called_once()
        self.assertTrue(mock_startfile.call_args.args[0].endswith("test.pdf"))

    def test_source_and_markdown_paths_call_startfile(self) -> None:
        """Both source_path and markdown_path values can be opened."""
        root = Path(__file__).resolve().parent / "_tmp" / f"links_{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        source_path = root / "source.txt"
        markdown_path = root / "note.md"
        source_path.write_text("source", encoding="utf-8")
        markdown_path.write_text("# note", encoding="utf-8")

        with patch("src.utils.os.startfile", create=True) as mock_startfile:
            source_success, source_message = open_local_file(str(source_path))
            markdown_success, markdown_message = open_local_file(str(markdown_path))

        self.assertTrue(source_success)
        self.assertTrue(markdown_success)
        self.assertEqual(source_message, "Opened successfully.")
        self.assertEqual(markdown_message, "Opened successfully.")
        self.assertEqual(mock_startfile.call_count, 2)

    def test_open_local_file_does_not_crash_on_startfile_error(self) -> None:
        """os.startfile errors are converted into a user-facing failure."""
        root = Path(__file__).resolve().parent / "_tmp" / f"links_{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        source_path = root / "source.txt"
        source_path.write_text("source", encoding="utf-8")

        with patch("src.utils.os.startfile", side_effect=OSError("blocked"), create=True):
            success, message = open_local_file(str(source_path))

        self.assertFalse(success)
        self.assertEqual(message, "Failed to open file.")


if __name__ == "__main__":
    unittest.main()
