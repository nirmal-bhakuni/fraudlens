"""Pure scoring functions for the retrieval evaluation.

No database and no model here, so everything is easy to test.
A question is "answerable" when it lists expected_sources. A question with no expected
sources is one the system should REFUSE (answer: I don't have enough information).
"""
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

SPLITS = ("dev", "test")


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expected_sources: tuple[str, ...]  # any one of these counts. Empty = should be refused
    split: str                         # "dev" chooses the cutoff, "test" checks it
    expected_answer: str               # for humans. The score does not use it

    @property
    def answerable(self) -> bool:
        return bool(self.expected_sources)


@dataclass(frozen=True)
class Retrieved:
    source: str
    score: float


@dataclass(frozen=True)
class Outcome:
    question: Question
    passed: bool
    first_rank: int | None  # 1-based rank of the first expected source among the results, else None


def load_questions(path: Path) -> list[Question]:
    # utf-8-sig also accepts a file that starts with a BOM (some Windows editors add one).
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    questions: list[Question] = []
    seen: set[str] = set()
    for item in raw:
        try:
            question = Question(
                id=item["id"],
                question=item["question"].strip(),
                expected_sources=tuple(item.get("expected_sources", [])),
                split=item["split"],
                expected_answer=item.get("expected_answer", ""),
            )
        except KeyError as missing:
            raise ValueError(f"Question {item.get('id', '?')} is missing the field {missing}") from None
        if question.id in seen:
            raise ValueError(f"Duplicate question id: {question.id}")
        if question.split not in SPLITS:
            raise ValueError(f"Question {question.id}: split must be one of {SPLITS}")
        seen.add(question.id)
        questions.append(question)
    return questions


def judge(question: Question, retrieved: list[Retrieved], cutoff: float) -> Outcome:
    """Would the API do the right thing for this question?

    Same rule as the API: a passage is used when its score is >= cutoff.
    - Answerable: pass if an expected document is among the passages that would be used.
    - Unanswerable: pass if no passage is used (the API would refuse).
    """
    used = [r for r in retrieved if r.score >= cutoff]
    first_rank = next(
        (i for i, r in enumerate(retrieved, 1) if r.source in question.expected_sources), None
    )
    if question.answerable:
        passed = any(r.source in question.expected_sources for r in used)
    else:
        passed = not used
    return Outcome(question, passed, first_rank)


def ratio(count: int, total: int) -> float:
    return count / total if total else 0.0


def summarize(outcomes: list[Outcome]) -> dict:
    answerable = [o for o in outcomes if o.question.answerable]
    refusals = [o for o in outcomes if not o.question.answerable]
    return {
        "questions": len(outcomes),
        "pass_rate": ratio(sum(o.passed for o in outcomes), len(outcomes)),
        "answerable": len(answerable),
        "answerable_pass_rate": ratio(sum(o.passed for o in answerable), len(answerable)),
        "unanswerable": len(refusals),
        "refusal_rate": ratio(sum(o.passed for o in refusals), len(refusals)),
        # Was an expected document the very first result, regardless of the cutoff?
        "hit_at_1": ratio(sum(o.first_rank == 1 for o in answerable), len(answerable)),
        # Mean reciprocal rank: 1 for rank 1, 0.5 for rank 2, 0 when not found.
        "mrr": ratio(sum(1 / o.first_rank for o in answerable if o.first_rank), len(answerable)),
    }


def sweep(questions: list[Question], retrieved_by_id: dict[str, list[Retrieved]],
          cutoffs: list[float], split: str) -> list[tuple[float, float]]:
    """Pass rate for each cutoff, using only the questions of one split."""
    subset = [q for q in questions if q.split == split]
    rows = []
    for cutoff in cutoffs:
        outcomes = [judge(q, retrieved_by_id[q.id], cutoff) for q in subset]
        rows.append((cutoff, summarize(outcomes)["pass_rate"]))
    return rows


def recommend_cutoff(rows: list[tuple[float, float]]) -> float:
    """The best pass rate wins. If several cutoffs tie, take the middle one, because
    the middle of a plateau is steadier than its edge."""
    best = max(rate for _, rate in rows)
    tied = [cutoff for cutoff, rate in rows if rate == best]
    return round(statistics.median(tied), 3)