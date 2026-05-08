"""Pure utility helpers for the workspace UI page.

Keeping these in a separate module avoids importing the full workspace page
(which has module-level side effects like creating directories) in unit tests.
"""

from __future__ import annotations


def folder_name_from_url(url: str) -> str:
    """Derive a workspace folder name from a repository URL.

    Strips the scheme, host, any embedded credentials, and the trailing
    ``.git`` suffix so that, e.g.,
    ``https://github.com/JacobMaldonado/pipeline_finance.git``
    becomes ``pipeline_finance``.
    """
    cleaned = url.strip().rstrip("/")
    last_segment = cleaned.split("/")[-1]
    return last_segment.removesuffix(".git")
