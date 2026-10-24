import pytest

from app.config import KNOWLEDGE_DIR
from app.rag.documents import chunk_document, load_documents


def test_short_text_is_one_chunk():
    assert chunk_document("One short paragraph.") == ["One short paragraph."]


def test_paragraphs_are_merged_up_to_the_limit():
    body = "aaa\n\nbbb\n\nccc"
    assert chunk_document(body, max_chars=100) == ["aaa\n\nbbb\n\nccc"]


def test_chunks_split_between_paragraphs_and_respect_the_limit():
    body = "\n\n".join(["x" * 40, "y" * 40, "z" * 40])
    chunks = chunk_document(body, max_chars=90)
    assert chunks == ["x" * 40 + "\n\n" + "y" * 40, "z" * 40]
    assert all(len(c) <= 90 for c in chunks)


def test_empty_body_gives_no_chunks():
    assert chunk_document("  \n\n  ") == []


def test_load_documents_reads_title_and_source(tmp_path):
    (tmp_path / "a.md").write_text("# Title A\n\nBody A.", encoding="utf-8")
    docs = load_documents(tmp_path)
    assert docs[0].source == "a.md"
    assert docs[0].title == "Title A"
    assert docs[0].body == "Body A."


def test_load_documents_rejects_missing_title(tmp_path):
    (tmp_path / "bad.md").write_text("No heading here.", encoding="utf-8")
    with pytest.raises(ValueError, match="first line"):
        load_documents(tmp_path)


def test_load_documents_rejects_empty_folder(tmp_path):
    with pytest.raises(ValueError, match="No .md files"):
        load_documents(tmp_path)


def test_real_knowledge_documents_are_valid():
    docs = load_documents(KNOWLEDGE_DIR)
    assert len(docs) >= 9
    assert len({d.title for d in docs}) == len(docs)  # no duplicate titles
    for doc in docs:
        assert doc.body.strip(), doc.source
        assert chunk_document(doc.body), doc.source