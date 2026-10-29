"""The Learn page's content: one Markdown file per topic in learn/, ending with a short quiz.

A topic file starts with "# Title", then the lesson, then "## Quiz" and blocks like:
Q: question / A) option / B) option / C) option / Answer: B / Why: explanation
"""
import re
from dataclasses import dataclass
from pathlib import Path

LEARN_DIR = Path(__file__).resolve().parent.parent / "learn"


@dataclass
class Question:
    text: str
    options: dict           # letter -> option, e.g. {"A": "It rises", "B": "It falls"}
    answer: str             # the letter of the right option
    why: str


@dataclass
class Topic:
    title: str
    lesson: str
    quiz: list


def parse_question(block):
    fields, options = {}, {}
    for line in block.strip().splitlines():
        line = line.strip()
        if option := re.match(r"^([A-D])\) (.+)$", line):
            options[option[1]] = option[2]
        elif field := re.match(r"^(Q|Answer|Why): (.+)$", line):
            fields[field[1]] = field[2]
        elif line:
            raise ValueError(f"Unexpected quiz line: {line!r}")
    missing = {"Q", "Answer", "Why"} - set(fields)
    if missing or len(options) < 2:
        raise ValueError(f"Incomplete question: {block.strip()[:60]!r}")
    if fields["Answer"] not in options:
        raise ValueError(f"The answer {fields['Answer']} is not one of the options: {fields['Q']!r}")
    return Question(fields["Q"], options, fields["Answer"], fields["Why"])


def parse_topic(text):
    lesson, _, quiz = text.partition("\n## Quiz\n")
    first_line, _, lesson = lesson.strip().partition("\n")
    if not first_line.startswith("# "):
        raise ValueError("A topic file must start with '# Title'")
    questions = [parse_question(block) for block in re.split(r"\n\s*\n", quiz.strip()) if block.strip()]
    return Topic(first_line[2:].strip(), lesson.strip(), questions)


def load_topics(folder=LEARN_DIR):
    """Every topic, in file name order (1_..., 2_..., ...)."""
    return [parse_topic(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.md"))]
