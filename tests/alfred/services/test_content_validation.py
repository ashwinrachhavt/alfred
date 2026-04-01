"""Tests for content validation utilities — error traceback detection."""

from alfred.services.doc_storage.utils import looks_like_error_content


class TestLooksLikeErrorContent:
    def test_empty_string(self):
        assert looks_like_error_content("") is False

    def test_normal_article(self):
        text = (
            "The Ozempicization of Everything. GLP-1 drugs are reshaping not just "
            "healthcare but the entire consumer economy. From food companies to theme "
            "parks, businesses are scrambling to adapt."
        )
        assert looks_like_error_content(text) is False

    def test_article_mentioning_errors(self):
        """An article that discusses error handling should not be flagged."""
        text = (
            "Python's error handling model uses exceptions. When you encounter a "
            "ModuleNotFoundError, check your PYTHONPATH. Tracebacks are your friend."
        )
        assert looks_like_error_content(text) is False

    def test_python_traceback(self):
        text = (
            'Traceback (most recent call last):\n'
            '  File "/app/main.py", line 42, in handle_request\n'
            '    result = db.execute(query)\n'
            'sqlalchemy.exc.ProgrammingError: column "foo" does not exist\n'
        )
        assert looks_like_error_content(text) is True

    def test_psycopg_error(self):
        text = (
            '  File "/site-packages/psycopg/cursor.py", line 97, in execute\n'
            '    raise ex.with_traceback(None)\n'
            'psycopg.errors.UndefinedColumn: column "pipeline_status" does not exist\n'
        )
        assert looks_like_error_content(text) is True

    def test_module_not_found_traceback(self):
        text = (
            'Traceback (most recent call last):\n'
            '  File "/app/test.py", line 5, in <module>\n'
            "    from alfred.models.thinking import ThinkingSessionRow\n"
            "ModuleNotFoundError: No module named 'alfred.models.thinking'\n"
        )
        assert looks_like_error_content(text) is True

    def test_single_pattern_not_enough(self):
        """A single match shouldn't trigger — could be a legitimate article."""
        text = "The Traceback (most recent call last) message confused many users."
        assert looks_like_error_content(text) is False
