"""Tests for job execution page — now a redirect notice to Prefect UI."""

from app.ui.pages.job_execution import job_execution_page


class TestJobExecutionPage:
    def test_page_function_is_callable(self):
        assert callable(job_execution_page)

    def test_page_function_accepts_execution_id(self):
        import inspect

        sig = inspect.signature(job_execution_page)
        assert "execution_id" in sig.parameters
