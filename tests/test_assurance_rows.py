"""Row grouping for the Assurance survey image.

Uses token positions only. Does not open a PDF or run OCR.
"""
from fetch_assurance import ROW_Y_TOLERANCE_PX, group_tokens


def token(y, x=0, text="89.7"):
    return {"y": y, "x": x, "text": text}


def test_empty_page_has_no_rows():
    assert group_tokens([]) == []


def test_one_token_is_one_row():
    rows = group_tokens([token(40, 3, "n/a")])
    assert len(rows) == 1
    assert rows[0]["tokens"][0]["text"] == "n/a"


def test_tokens_within_tolerance_are_one_row():
    rows = group_tokens([
        token(0, 10, "Education Quality"),
        token(ROW_Y_TOLERANCE_PX, 400, "89.7"),
    ])
    assert len(rows) == 1
    assert [item["text"] for item in rows[0]["tokens"]] == ["Education Quality", "89.7"]


def test_tokens_farther_apart_are_separate_rows():
    rows = group_tokens([token(0), token(ROW_Y_TOLERANCE_PX + 1)])
    assert len(rows) == 2


def test_a_later_token_uses_the_row_mean():
    rows = group_tokens([token(0), token(10), token(30)])
    assert [len(row["tokens"]) for row in rows] == [2, 1]
