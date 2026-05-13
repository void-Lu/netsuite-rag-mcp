from __future__ import annotations

from netsuite_rag_mcp.models import Chunk, SourceDocument


def chunk_document(document: SourceDocument) -> list[Chunk]:
    sections = _split_h2_sections(document.body)
    if not sections:
        sections = [("Document", document.body)]

    chunks: list[Chunk] = []
    for index, (heading, text) in enumerate(sections):
        content = text.strip()
        if not content:
            continue
        metadata = dict(document.frontmatter)
        metadata.update(
            {
                "doc_id": document.doc_id,
                "chunk_index": index,
                "source_path": document.source_path,
                "heading": heading,
                "updated_at": document.updated_at,
            }
        )
        chunks.append(
            Chunk(
                id=f"{document.doc_id}:{index}",
                doc_id=document.doc_id,
                chunk_index=index,
                source_path=document.source_path,
                heading=heading,
                text=content,
                metadata=metadata,
            )
        )
    return chunks


def _split_h2_sections(markdown: str) -> list[tuple[str, str]]:
    lines = markdown.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence

        if not in_fence and line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip()
            current_lines = [line]
            continue

        if current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_lines))

    return [(heading, "\n".join(section_lines)) for heading, section_lines in sections]