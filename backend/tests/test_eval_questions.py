from app.config import BASE_DIR, KNOWLEDGE_DIR
from app.rag.eval_metrics import load_questions

QUESTIONS = BASE_DIR / "eval" / "questions.json"


def test_question_set_has_the_required_size_and_balance():
    questions = load_questions(QUESTIONS)
    assert 30 <= len(questions) <= 50
    assert sum(1 for q in questions if not q.answerable) >= 6  # questions the system should refuse
    for split in ("dev", "test"):
        in_split = [q for q in questions if q.split == split]
        assert len(in_split) >= 10
        assert any(q.answerable for q in in_split)
        assert any(not q.answerable for q in in_split)


def test_every_expected_source_exists_and_every_document_has_a_question():
    questions = load_questions(QUESTIONS)
    docs = {path.name for path in KNOWLEDGE_DIR.glob("*.md")}
    expected = {s for q in questions for s in q.expected_sources}
    assert expected <= docs, f"questions point to missing documents: {sorted(expected - docs)}"
    assert docs <= expected, f"documents without any question: {sorted(docs - expected)}"


def test_knowledge_base_has_between_15_and_25_documents():
    assert 15 <= len(list(KNOWLEDGE_DIR.glob("*.md"))) <= 25


def test_every_question_has_an_expected_answer():
    for q in load_questions(QUESTIONS):
        assert q.expected_answer.strip(), q.id