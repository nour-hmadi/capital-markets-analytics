"""The Learn notes for the assistant (RAG), with fake embeddings: no internet, the same results every time."""
from learn_content import load_topics
from notes import Notes, load_chunks


def test_every_lesson_becomes_paragraph_chunks():
    chunks = load_chunks()
    assert {chunk.lesson for chunk in chunks} == {topic.title for topic in load_topics()}
    assert all(chunk.text and "Answer:" not in chunk.text for chunk in chunks)      # the quizzes are left out
    assert any(chunk.text.startswith("**DV01**") for chunk in chunks)               # one paragraph, one idea


def test_a_question_finds_the_closest_notes(fake_embed):
    found = Notes(load_chunks(), fake_embed).search("What does DV01 mean for a bond?")
    assert len(found) == 3
    assert found[0].lesson == "Rate risk (DV01)"


def test_the_notes_become_vectors_once_and_each_question_every_time(fake_embed):
    notes = Notes(load_chunks(), fake_embed)
    notes.search("What is DV01?")
    notes.search("What is a forward?")
    documents, *questions = fake_embed.calls
    assert len(documents) == len(notes.chunks) and documents[0].startswith("title: ")
    assert questions == [["task: search result | query: What is DV01?"],
                         ["task: search result | query: What is a forward?"]]
