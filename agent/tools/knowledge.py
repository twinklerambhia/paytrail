from agent.errors import ToolInputError
from knowledge_base.loader import search


def search_support_knowledge(
    query: str,
    issue_type: str | None = None,
    error_codes: list[str] | None = None,
    top_k: int = 3,
    language: str = "en",
) -> dict:
    """Read-only SOP/error-code retrieval. Guidance, not authorization."""
    if not query or not query.strip():
        raise ToolInputError("query must be a non-empty string.")
    if not (1 <= top_k <= 5):
        raise ToolInputError("top_k must be between 1 and 5.")
    if language not in ("en", "hi", "mr"):
        raise ToolInputError(f"Unsupported language={language!r}.")

    return search(query, issue_type=issue_type, error_codes=error_codes, top_k=top_k, language=language)
