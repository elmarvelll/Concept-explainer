from rag.topic_finder import find_topic

OUTLINE = {
    "textbook": "Sample Engineering Mathematics",
    "chapters": [
        {
            "title": "Laplace Transforms",
            "number": None,
            "level": 1,
            "page": 300,
            "children": [
                {"title": "Introduction to Laplace Transforms", "number": None, "level": 2, "page": 301, "children": []},
                {"title": "Definition", "number": None, "level": 2, "page": 303, "children": []},
                {
                    "title": "Properties of Laplace Transforms",
                    "number": None,
                    "level": 2,
                    "page": 307,
                    "children": [
                        {"title": "Linearity", "number": None, "level": 3, "page": 308, "children": []},
                        {"title": "First Shifting Theorem", "number": None, "level": 3, "page": 310, "children": []},
                    ],
                },
                {"title": "Inverse Laplace Transforms", "number": None, "level": 2, "page": 315, "children": []},
            ],
        },
        {
            "title": "Fourier Series",
            "number": None,
            "level": 1,
            "page": 400,
            "children": [
                {"title": "Periodic Functions", "number": None, "level": 2, "page": 401, "children": []},
            ],
        },
    ],
}


def test_finds_exact_title():
    result = find_topic("Laplace Transforms", OUTLINE)
    assert result["success"] is True
    assert result["data"]["matched_title"] == "Laplace Transforms"
    subtopic_titles = [c["title"] for c in result["data"]["subtopics"]]
    assert subtopic_titles == [
        "Introduction to Laplace Transforms",
        "Definition",
        "Properties of Laplace Transforms",
        "Inverse Laplace Transforms",
    ]


def test_finds_lowercase_and_singular_variant():
    result = find_topic("laplace transform", OUTLINE)
    assert result["success"] is True
    assert result["data"]["matched_title"] == "Laplace Transforms"


def test_finds_nested_subtopic_with_breadcrumb():
    result = find_topic("Inverse Laplace Transform", OUTLINE)
    assert result["success"] is True
    assert result["data"]["matched_title"] == "Inverse Laplace Transforms"
    assert result["data"]["breadcrumb"] == ["Laplace Transforms"]


def test_deeply_nested_subtopic():
    result = find_topic("first shifting theorem", OUTLINE)
    assert result["success"] is True
    assert result["data"]["matched_title"] == "First Shifting Theorem"
    assert result["data"]["breadcrumb"] == ["Laplace Transforms", "Properties of Laplace Transforms"]
    assert result["data"]["subtopics"] == []


def test_topic_not_found_returns_clear_error_not_hallucination():
    result = find_topic("Quantum Chromodynamics", OUTLINE)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_empty_outline():
    result = find_topic("Anything", {"textbook": "Empty", "chapters": []})
    assert result["success"] is False
