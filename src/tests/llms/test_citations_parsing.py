from typing import Any

import pytest
from llama_index.core.schema import TextNode

from src.llm.parser.citation_parser import CITATION_TEXT, CitationParser


def make_citation(url: str, title: str) -> str:
    """Helper to create expected citation text."""
    return CITATION_TEXT.format(url=url, title=title)


examples: list[Any] = [
    (
        "Bei Bedarf kann diese Summe auf 500.000 Euro erhöht werden. [doc1][doc2][doc3]",
        f'Bei Bedarf kann diese Summe auf 500.000 Euro erhöht werden. {make_citation("fake_1.url", "Titel 1")}{make_citation("fake_2.url", "Titel 2")}{make_citation("fake_3.url", "Titel 3")}',
    ),
    ("Wrong [docX][doc1.1], Right [doc1].", f'Wrong , Right {make_citation("fake_1.url", "Titel 1")}.'),
    (
        "[doc1][doc2] beginning.",
        f'{make_citation("fake_1.url", "Titel 1")}{make_citation("fake_2.url", "Titel 2")} beginning.',
    ),
    ("Not existing [doc100]", "Not existing "),
    (
        "Unusual [doc2] order [doc4][doc1][doc2][doc1]",
        f'Unusual {make_citation("fake_2.url", "Titel 2")} order {make_citation("fake_4.url", "Titel 4")}{make_citation("fake_1.url", "Titel 1")}',
    ),
    (
        "Made consecutive [doc2][doc3]",
        f'Made consecutive {make_citation("fake_2.url", "Titel 2")}{make_citation("fake_3.url", "Titel 3")}',
    ),
    (
        "[doc3] high refs [doc2]",
        f'{make_citation("fake_3.url", "Titel 3")} high refs {make_citation("fake_2.url", "Titel 2")}',
    ),
    (
        "Dies wird in [doc2] und [doc4] angegeben.",
        f'Dies wird in {make_citation("fake_2.url", "Titel 2")} und {make_citation("fake_4.url", "Titel 4")} angegeben.',
    ),
    (
        "Dies wird in [doc4] und [doc1] angegeben.",
        f'Dies wird in {make_citation("fake_4.url", "Titel 4")} und {make_citation("fake_1.url", "Titel 1")} angegeben.',
    ),
    (
        "Dies wird in [doc4] und [doc1], [doc3] angegeben.",
        f'Dies wird in {make_citation("fake_4.url", "Titel 4")} und {make_citation("fake_1.url", "Titel 1")}, {make_citation("fake_3.url", "Titel 3")} angegeben.',
    ),
]


@pytest.mark.parametrize("answer, processed", examples)
def test_answer_parsing(answer: str, processed: str):
    sources = [TextNode(text=f"doc_{i}", metadata={"url": f"fake_{i}.url", "title": f"Titel {i}"}) for i in range(1, 5)]

    answer_parsed = CitationParser().parse(answer=answer, source_documents=sources)
    assert answer_parsed == processed


def test_fallback_to_url_when_no_title():
    """Test that URL is used as display text when title is missing."""
    sources = [
        TextNode(text="doc_1", metadata={"url": "https://moodle.ki-campus.org/course/view.php?id=123"}),
    ]
    answer = "Schau dir das an [doc1]."
    
    answer_parsed = CitationParser().parse(answer=answer, source_documents=sources)
    
    assert "moodle.ki-campus.org" in answer_parsed
    assert "[doc1]" not in answer_parsed


def test_long_title_is_truncated():
    """Test that very long titles are truncated."""
    long_title = "Dies ist ein sehr langer Titel der mehr als fünfzig Zeichen hat und daher gekürzt werden sollte"
    sources = [
        TextNode(text="doc_1", metadata={"url": "https://example.com", "title": long_title}),
    ]
    answer = "Info hier [doc1]."
    
    answer_parsed = CitationParser().parse(answer=answer, source_documents=sources)
    
    assert "..." in answer_parsed
    assert long_title not in answer_parsed

