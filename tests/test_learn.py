"""The Learn page's content: every topic has a lesson and a quiz whose answers are among the options."""
import pytest

from learn_content import LEARN_DIR, load_topics, parse_topic

TOPIC_FILES = sorted(LEARN_DIR.glob("*.md"))


def test_the_five_topics_in_order():
    assert [topic.title for topic in load_topics()] == [
        "Equities", "Bonds", "Rate risk (DV01)", "FX forwards", "Trade lifecycle"]


@pytest.mark.parametrize("path", TOPIC_FILES, ids=lambda path: path.name)
def test_every_topic_has_a_lesson_and_three_questions(path):
    topic = parse_topic(path.read_text(encoding="utf-8"))
    assert len(topic.lesson) > 500
    assert len(topic.quiz) == 3
    for question in topic.quiz:
        assert question.answer in question.options and question.why


@pytest.mark.parametrize("quiz", [
    "Q: Which?\nA) One\nB) Two\nAnswer: C\nWhy: C is not an option",
    "Q: Which?\nA) One\nB) Two\nWhy: the answer line is missing",
    "Q: Which?\nA) One\nB) Two\nAnswer: A\nWhy: fine\nA stray line",
])
def test_a_broken_quiz_is_rejected(quiz):
    with pytest.raises(ValueError):
        parse_topic(f"# Topic\n\nThe lesson.\n\n## Quiz\n\n{quiz}\n")
