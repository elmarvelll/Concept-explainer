from types import SimpleNamespace

from rag.textbook_outline import _extract_number, find_section_for_page, walk_outline


def bookmark(title):
    return SimpleNamespace(title=title)


def test_extract_number():
    assert _extract_number("2.5 Series Resistors") == "2.5"
    assert _extract_number("Chapter 2 Basic Laws") == "2"
    assert _extract_number("Introduction") is None
    assert _extract_number("14.7.1 Lowpass Filter") == "14.7.1"


def test_walk_outline_preserves_hierarchy_and_order():
    # Mirrors a fixture like:
    # Chapter 5
    #   5.1 Introduction
    #   5.2 Definition
    #   5.3 Properties
    #       5.3.1 Linearity
    #       5.3.2 First Shifting Theorem
    #   5.4 Inverse Laplace Transform
    raw = [
        bookmark("Chapter 5 Laplace Transforms"),
        [
            bookmark("5.1 Introduction"),
            bookmark("5.2 Definition"),
            bookmark("5.3 Properties"),
            [
                bookmark("5.3.1 Linearity"),
                bookmark("5.3.2 First Shifting Theorem"),
            ],
            bookmark("5.4 Inverse Laplace Transform"),
        ],
    ]

    pages = {
        "Chapter 5 Laplace Transforms": 100,
        "5.1 Introduction": 101,
        "5.2 Definition": 103,
        "5.3 Properties": 107,
        "5.3.1 Linearity": 108,
        "5.3.2 First Shifting Theorem": 110,
        "5.4 Inverse Laplace Transform": 115,
    }

    tree = walk_outline(raw, get_page=lambda item: pages[item.title])

    assert len(tree) == 1
    chapter = tree[0]
    assert chapter["title"] == "Chapter 5 Laplace Transforms"
    assert chapter["level"] == 1
    assert chapter["page"] == 100

    children = chapter["children"]
    assert [c["title"] for c in children] == [
        "5.1 Introduction",
        "5.2 Definition",
        "5.3 Properties",
        "5.4 Inverse Laplace Transform",
    ]
    assert all(c["level"] == 2 for c in children)

    properties = children[2]
    assert [c["title"] for c in properties["children"]] == [
        "5.3.1 Linearity",
        "5.3.2 First Shifting Theorem",
    ]
    assert all(c["level"] == 3 for c in properties["children"])
    assert properties["children"][0]["number"] == "5.3.1"


def test_walk_outline_handles_unresolvable_page():
    raw = [bookmark("Broken Bookmark")]

    def get_page(item):
        raise ValueError("can't resolve")

    tree = walk_outline(raw, get_page=get_page)
    assert tree[0]["page"] is None


SAMPLE_OUTLINE = {
    "textbook": "Sample",
    "chapters": [
        {
            "title": "Chapter 2 Basic Laws",
            "number": "2",
            "level": 1,
            "page": 50,
            "children": [
                {"title": "2.1 Introduction", "number": "2.1", "level": 2, "page": 51, "children": []},
                {"title": "2.2 Ohm's Law", "number": "2.2", "level": 2, "page": 52, "children": []},
                {"title": "2.4 Kirchhoff's Laws", "number": "2.4", "level": 2, "page": 59, "children": []},
            ],
        },
        {
            "title": "Chapter 3 Methods of Analysis",
            "number": "3",
            "level": 1,
            "page": 103,
            "children": [
                {"title": "3.2 Nodal Analysis", "number": "3.2", "level": 2, "page": 104, "children": []},
            ],
        },
    ],
}


def test_find_section_for_page():
    assert find_section_for_page(55, SAMPLE_OUTLINE) == {
        "chapter": "Chapter 2 Basic Laws",
        "section": "2.2 Ohm's Law",
    }
    assert find_section_for_page(60, SAMPLE_OUTLINE) == {
        "chapter": "Chapter 2 Basic Laws",
        "section": "2.4 Kirchhoff's Laws",
    }
    assert find_section_for_page(105, SAMPLE_OUTLINE) == {
        "chapter": "Chapter 3 Methods of Analysis",
        "section": "3.2 Nodal Analysis",
    }


def test_find_section_for_page_before_anything():
    assert find_section_for_page(0, SAMPLE_OUTLINE) == {"chapter": None, "section": None}


# Regression test: some textbooks (including the one this project ships)
# nest "Chapter N" under a coarser "Part N" grouping at level 1 — "chapter"
# must still resolve to the actual chapter, not the part.
OUTLINE_WITH_PARTS = {
    "textbook": "Sample",
    "chapters": [
        {
            "title": "PART 1 DC Circuits",
            "number": None,
            "level": 1,
            "page": 24,
            "children": [
                {
                    "title": "Chapter 2 Basic Laws",
                    "number": "2",
                    "level": 2,
                    "page": 50,
                    "children": [
                        {"title": "2.2 Ohm's Law", "number": "2.2", "level": 3, "page": 52, "children": []},
                    ],
                },
            ],
        },
    ],
}


def test_find_section_for_page_with_part_wrapper():
    assert find_section_for_page(55, OUTLINE_WITH_PARTS) == {
        "chapter": "Chapter 2 Basic Laws",
        "section": "2.2 Ohm's Law",
    }
