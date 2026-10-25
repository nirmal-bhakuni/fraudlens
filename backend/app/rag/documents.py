"""Read knowledge documents and split them into chunks."""
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Document:
    source: str  # file name
    title: str
    body: str


def load_documents(docs_dir: Path) -> list[Document]:
    """Every .md file must start with a line like '# Title'."""
    files = sorted(Path(docs_dir).glob("*.md"))
    if not files:
        raise ValueError(f"No .md files found in {docs_dir}")
    documents = []
    for path in files:
        lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
        if not lines or not lines[0].startswith("# "):
            raise ValueError(f"{path.name}: the first line must be '# Title'")
        documents.append(Document(
            source=path.name,
            title=lines[0][2:].strip(),
            body="\n".join(lines[1:]).strip(),
        ))
    return documents


def chunk_document(body: str, max_chars: int = 700) -> list[str]:
    """Join paragraphs until a chunk would pass max_chars. We never cut inside a paragraph.

    A single paragraph longer than max_chars stays whole.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks