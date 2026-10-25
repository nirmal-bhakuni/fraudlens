import json

import pytest

from app.rag.eval_metrics import (
    Question, Retrieved, judge, load_questions, recommend_cutoff, summarize, sweep,
)


def q(id="q1", sources=("a.md",), split="dev"):
    return Question(id=id, question="question text", expected_sources=tuple(sources),
                    split=split, expected_answer="")


def r(source, score):
    return Retrieved(source, score)


def test_answerable_passes_when_expected_source_is_above_cutoff():
    outcome = judge(q(), [r("b.md", 0.5), r("a.md", 0.4)], cutoff=0.3)
    assert outcome.passed
    assert outcome.first_rank == 2


def test_answerable_fails_when_expected_source_is_too_weak():
    outcome = judge(q(), [r("b.md", 0.5), r("a.md", 0.2)], cutoff=0.3)
    assert not outcome.passed
    assert outcome.first_rank == 2  # it was found, but too weak to be used


def test_answerable_fails_when_expected_source_is_not_retrieved():
    outcome = judge(q(), [r("b.md", 0.9)], cutoff=0.3)
    assert not outcome.passed
    assert outcome.first_rank is None


def test_any_of_several_expected_sources_is_enough():
    assert judge(q(sources=("a.md", "c.md")), [r("c.md", 0.6)], 0.3).passed


def test_unanswerable_passes_only_when_nothing_is_above_cutoff():
    refuse = q(sources=())
    assert judge(refuse, [r("a.md", 0.29)], 0.3).passed
    assert not judge(refuse, [r("a.md", 0.31)], 0.3).passed
    assert judge(refuse, [], 0.3).passed


def test_score_equal_to_cutoff_counts_as_used():
    # the same rule as the API: score >= cutoff
    assert judge(q(), [r("a.md", 0.3)], 0.3).passed


def test_summarize_numbers():
    outcomes = [
        judge(q("a", ("a.md",)), [r("a.md", 0.9)], 0.3),                  # pass, rank 1
        judge(q("b", ("a.md",)), [r("x.md", 0.8), r("a.md", 0.7)], 0.3),  # pass, rank 2
        judge(q("c", ("a.md",)), [r("x.md", 0.8)], 0.3),                  # fail, not found
        judge(q("d", ()), [r("x.md", 0.1)], 0.3),                         # refused correctly
    ]
    s = summarize(outcomes)
    assert s["questions"] == 4
    assert s["pass_rate"] == pytest.approx(3 / 4)
    assert s["answerable"] == 3
    assert s["unanswerable"] == 1
    assert s["answerable_pass_rate"] == pytest.approx(2 / 3)
    assert s["refusal_rate"] == 1.0
    assert s["hit_at_1"] == pytest.approx(1 / 3)
    assert s["mrr"] == pytest.approx((1 + 0.5 + 0) / 3)


def test_summarize_empty_group_does_not_divide_by_zero():
    s = summarize([])
    assert s["pass_rate"] == 0.0
    assert s["mrr"] == 0.0


def test_sweep_uses_only_the_chosen_split_and_recommends_the_best_cutoff():
    questions = [q("a", ("a.md",), "dev"), q("b", (), "dev"), q("c", ("a.md",), "test")]
    retrieved = {"a": [r("a.md", 0.45)], "b": [r("a.md", 0.35)], "c": [r("a.md", 0.9)]}
    rows = sweep(questions, retrieved, [0.2, 0.3, 0.4, 0.5], "dev")
    assert rows == [(0.2, 0.5), (0.3, 0.5), (0.4, 1.0), (0.5, 0.5)]
    assert recommend_cutoff(rows) == 0.4


def test_recommendation_takes_the_middle_of_a_tie():
    rows = [(0.2, 0.5), (0.3, 1.0), (0.4, 1.0), (0.5, 1.0), (0.6, 0.5)]
    assert recommend_cutoff(rows) == 0.4


ITEM = {"id": "q1", "question": "What is x?", "expected_sources": ["a.md"], "split": "dev", "expected_answer": "x"}


def write(tmp_path, items, encoding="utf-8"):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(items), encoding=encoding)
    return path


def test_load_questions_reads_the_fields(tmp_path):
    [loaded] = load_questions(write(tmp_path, [ITEM]))
    assert loaded.id == "q1"
    assert loaded.expected_sources == ("a.md",)
    assert loaded.answerable


def test_question_without_sources_is_unanswerable(tmp_path):
    [loaded] = load_questions(write(tmp_path, [{**ITEM, "expected_sources": []}]))
    assert not loaded.answerable


def test_load_questions_accepts_a_file_with_a_bom(tmp_path):
    assert len(load_questions(write(tmp_path, [ITEM], encoding="utf-8-sig"))) == 1


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        load_questions(write(tmp_path, [ITEM, ITEM]))


def test_bad_split_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="split"):
        load_questions(write(tmp_path, [{**ITEM, "split": "validation"}]))


def test_missing_field_is_rejected(tmp_path):
    bad = {k: v for k, v in ITEM.items() if k != "question"}
    with pytest.raises(ValueError, match="missing"):
        load_questions(write(tmp_path, [bad]))