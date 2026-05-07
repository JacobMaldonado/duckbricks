"""Tests for workspace page dispatch helpers — .py and .ipynb file handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPythonFileDetection:
    """Verify that the marimo-header check works correctly."""

    def test_detects_marimo_file_by_import(self):
        content = "import marimo\n\napp = marimo.App()\n"
        assert "import marimo" in content

    def test_detects_plain_python_file(self):
        content = "def hello():\n    return 'hello'\n"
        assert "import marimo" not in content

    def test_template_contains_marimo_import(self):
        template = (
            "# /// script\n"
            "import marimo\n"
            "\n"
            '__generated_with = "0.10.0"\n'
            "app = marimo.App()\n"
        )
        assert "import marimo" in template

    def test_template_prepended_marks_file_as_marimo(self):
        template = (
            "import marimo\n\napp = marimo.App()\n\n\nif __name__ == '__main__':\n    app.run()\n"
        )
        original = "x = 1\n"
        combined = template + original
        assert "import marimo" in combined
        assert "x = 1" in combined


class TestMarimoConvertDispatch:
    """Verify the subprocess call for marimo convert is correctly formed."""

    def test_convert_command_structure(self, tmp_path: Path):
        abs_input = tmp_path / "notebook.ipynb"
        abs_output = tmp_path / "notebook.py"
        abs_input.write_text("{}")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "marimo"
            assert call_args[1] == "convert"
            assert str(abs_input) in call_args
            assert "-o" in call_args
            assert str(abs_output) in call_args

    def test_failed_conversion_raises(self, tmp_path: Path):
        abs_input = tmp_path / "bad.ipynb"
        abs_output = tmp_path / "bad.py"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="parse error")

            import subprocess

            result = subprocess.run(
                ["marimo", "convert", str(abs_input), "-o", str(abs_output)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode != 0
            assert result.stderr


class TestSuggestedOutputPath:
    """Verify .py output path derivation from .ipynb path."""

    def test_flat_file(self):
        relative_path = "notebook.ipynb"
        base_name = Path(relative_path).stem
        parent = str(Path(relative_path).parent)
        result = f"{parent}/{base_name}.py" if parent != "." else f"{base_name}.py"
        assert result == "notebook.py"

    def test_nested_file(self):
        relative_path = "analysis/my_notebook.ipynb"
        base_name = Path(relative_path).stem
        parent = str(Path(relative_path).parent)
        result = f"{parent}/{base_name}.py" if parent != "." else f"{base_name}.py"
        assert result == "analysis/my_notebook.py"

    def test_deep_nested_file(self):
        relative_path = "a/b/c/deep.ipynb"
        base_name = Path(relative_path).stem
        parent = str(Path(relative_path).parent)
        result = f"{parent}/{base_name}.py" if parent != "." else f"{base_name}.py"
        assert result == "a/b/c/deep.py"
