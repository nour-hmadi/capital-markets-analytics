"""The Learn notes, searchable by meaning (RAG): the assistant's search_notes tool reads them.

Each paragraph of a lesson is one chunk. An embedding model turns each chunk into a vector once, on the first
search, and each question into a vector every time. The closest chunks (cosine similarity) go to the model.
"""
import re
from dataclasses import dataclass

import numpy as np
from google import genai
from google.genai import types

from learn_content import load_topics

EMBEDDING_MODEL = "gemini-embedding-2"       # Google's embedding model, free on the Gemini API's free tier


@dataclass
class Chunk:
    lesson: str
    text: str


def load_chunks(topics=None):
    """One chunk per paragraph of each lesson. The quizzes are left out."""
    topics = topics if topics is not None else load_topics()
    return [Chunk(topic.title, paragraph.strip())
            for topic in topics for paragraph in re.split(r"\n\s*\n", topic.lesson) if paragraph.strip()]


def gemini_embedder(api_key):
    """A function that turns texts into vectors with Gemini: one request for a whole list of texts."""
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))

    def embed(texts):
        result = client.models.embed_content(model=EMBEDDING_MODEL,
                                             contents=[{"parts": [{"text": text}]} for text in texts])
        return [embedding.values for embedding in result.embeddings]
    return embed


class Notes:
    """The chunks and their vectors. gemini-embedding-2 takes the task inside the text, not as a setting."""

    def __init__(self, chunks, embed):
        self.chunks = chunks
        self.embed = embed
        self.vectors = None                     # made on the first search, then reused

    def search(self, question, k=3):
        """The k chunks closest in meaning to the question."""
        if self.vectors is None:
            self.vectors = np.array(self.embed([f"title: {chunk.lesson} | text: {chunk.text}"
                                                for chunk in self.chunks]))
        query = np.array(self.embed([f"task: search result | query: {question}"])[0])
        cosine = self.vectors @ query / (np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(query))
        return [self.chunks[i] for i in np.argsort(-cosine)[:k]]
