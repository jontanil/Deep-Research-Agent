from src.agents.research import clean_output


def test_clean_output_converts_citations_to_numbers():
    content, references = clean_output(
        "See [[[Alpha — https://a.com]]] and [[[Beta — https://b.com]]]"
    )
    assert "[1]" in content and "[2]" in content
    assert references == {"Alpha — https://a.com": 1, "Beta — https://b.com": 2}


def test_clean_output_deduplicates_citations():
    content, references = clean_output(
        "First [[[Alpha — https://a.com]]] then again [[[Alpha — https://a.com]]]"
    )
    assert list(references.keys()) == ["Alpha — https://a.com"]
    assert references["Alpha — https://a.com"] == 1
    assert content.count("[1]") == 2


def test_clean_output_no_citations_unchanged():
    content, references = clean_output("plain text without any citation markers")
    assert content == "plain text without any citation markers"
    assert references == {}