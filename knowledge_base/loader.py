"""Keyword + metadata retrieval over the synthetic SOP knowledge base.

No embeddings/FAISS for the hackathon MVP (brief section 7). Markdown files
carry YAML-ish frontmatter (hand-parsed — scalars and one-level [a, b] lists
only, so no new dependency for something this small) and are chunked by
`##` headers. error_codes.json is folded in as one synthetic chunk per code
so "DEVICE_UNREACHABLE" is searchable the same way an SOP paragraph is.
"""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from django.conf import settings


@dataclass
class Chunk:
    document_id: str
    chunk_id: str
    title: str
    content: str
    issue_type: str | None
    error_codes: list[str] = field(default_factory=list)
    source_version: str = "1.0"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    header, body = text[3:end].strip(), text[end + 4 :].lstrip("\n")
    meta: dict = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip("\"'")
    return meta, body


def _chunk_body(document_id: str, body: str) -> list[tuple[str, str]]:
    """Split on '## ' headers; returns [(heading, section_text), ...]."""
    sections = re.split(r"\n(?=## )", body.strip())
    chunks = []
    for idx, section in enumerate(sections, start=1):
        heading_match = re.match(r"##\s+(.+)", section)
        heading = heading_match.group(1).strip() if heading_match else "Overview"
        chunks.append((heading, section.strip()))
    return chunks


def _load_markdown_chunks(kb_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for md_path in sorted(kb_dir.glob("*.md")):
        meta, body = _parse_frontmatter(md_path.read_text(encoding="utf-8"))
        document_id = meta.get("document_id", md_path.stem.upper())
        title = meta.get("title", md_path.stem)
        issue_type = meta.get("issue_type")
        error_codes = meta.get("error_codes", [])
        version = meta.get("version", "1.0")
        for idx, (heading, text) in enumerate(_chunk_body(document_id, body), start=1):
            chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_id=f"{document_id}_CHUNK_{idx:02d}",
                    title=f"{title} — {heading}" if heading != "Overview" else title,
                    content=text,
                    issue_type=issue_type,
                    error_codes=error_codes,
                    source_version=version,
                )
            )
    return chunks


def _load_error_code_chunks(kb_dir: Path) -> list[Chunk]:
    path = kb_dir / "error_codes.json"
    if not path.exists():
        return []
    catalogue = json.loads(path.read_text(encoding="utf-8"))
    chunks = []
    for code, info in catalogue.items():
        chunks.append(
            Chunk(
                document_id="ERROR_CODES",
                chunk_id=f"ERROR_CODES_{code}",
                title=f"Error code: {code}",
                content=f"{info.get('meaning', '')} Recommended action: {info.get('recommended_action', '')}",
                issue_type=info.get("issue_type"),
                error_codes=[code],
                source_version="1.0",
            )
        )
    return chunks


@lru_cache(maxsize=1)
def _index() -> list[Chunk]:
    kb_dir = Path(settings.KNOWLEDGE_BASE_DIR)
    return _load_markdown_chunks(kb_dir) + _load_error_code_chunks(kb_dir)


def _score(chunk: Chunk, query_terms: set[str], issue_type: str | None, error_codes: list[str]) -> float:
    haystack = f"{chunk.title} {chunk.content}".lower()
    term_hits = sum(1 for term in query_terms if term and term in haystack)
    score = term_hits / max(len(query_terms), 1)
    if issue_type and chunk.issue_type == issue_type:
        score += 0.3
    if error_codes and any(code in chunk.error_codes for code in error_codes):
        score += 0.3
    return min(score, 1.0)


def search(
    query: str,
    issue_type: str | None = None,
    error_codes: list[str] | None = None,
    top_k: int = 3,
    language: str = "en",
) -> dict:
    error_codes = error_codes or []
    query_terms = {t for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) > 2}

    scored = [
        (chunk, _score(chunk, query_terms, issue_type, error_codes))
        for chunk in _index()
    ]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    results = [
        {
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "title": chunk.title,
            "content": chunk.content,
            "issue_type": chunk.issue_type,
            "matched_error_codes": [c for c in chunk.error_codes if c in error_codes] or chunk.error_codes,
            "relevance_score": round(score, 2),
            "source_version": chunk.source_version,
        }
        for chunk, score in scored[: max(1, min(top_k, 5))]
    ]
    return {
        "results": results,
        "retrieval_method": "keyword_and_metadata",
        "query_language": language,
        "filters_applied": {"issue_type": issue_type, "error_codes": error_codes},
    }
