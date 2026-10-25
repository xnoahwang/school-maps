"""Row grouping for the Assurance survey image.

Uses token positions only. Does not open a PDF or run OCR.
"""
from fetch_assurance import (
    ROW_Y_TOLERANCE_PX, garbled_number, group_tokens, is_results_report,
    measures_from_text, parse_measure_rows, results_report_urls,
)


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


def row_of(*parts):
    return {"tokens": [token(y, x, text) for y, x, text in parts]}


def test_misspelled_labels_keep_the_current_year_number():
    # Valley View's table, with the spellings RapidOCR produced.
    rows = [
        row_of((238, 200, "Student Leaming Engagement"), (238, 600, "81.8"), (238, 680, "74.6")),
        row_of((257, 200, "Ciizenship"), (257, 600, "68.8"), (257, 680, "65.7")),
        row_of(
            (393, 180, "Educaltion Quality"),
            (393, 400, "Welcoming, Caring, Respectful and Safe"),
            (393, 600, "82.9"),
            (393, 680, "84.7"),
        ),
        row_of((414, 200, "Learning Environments (WCRSLE)"), (414, 600, "6'69"), (414, 680, "73.0")),
        row_of((435, 200, "Arcess to Supports and Services"), (435, 600, "6'69"), (435, 680, "66.4")),
        row_of((454, 200, "Parental lnvolvement"), (454, 600, "68.5"), (454, 680, "67.7")),
    ]
    found, pending = parse_measure_rows(rows)
    assert found["learning_engagement"] == 81.8
    assert found["citizenship"] == 68.8
    assert found["education_quality"] == 82.9
    assert found["parental_involvement"] == 68.5
    assert found.get("safe_caring") != 82.9
    assert {item["key"] for item in pending} == {"safe_caring", "access_supports"}
    assert garbled_number("6'69")
    assert not garbled_number("82.9")
    assert not garbled_number("n/a")


def test_joined_ocr_spellings_still_match():
    found, pending = parse_measure_rows([
        row_of((10, 100, "Student LeamingEnqagement"), (10, 600, "83.9")),
        row_of((30, 100, "Cifizenship"), (30, 600, "82.9")),
    ])
    assert found["learning_engagement"] == 83.9
    assert found["citizenship"] == 82.9
    assert pending == []


def test_a_published_blank_stays_blank():
    found, pending = parse_measure_rows([
        row_of((10, 100, "Citizenship"), (10, 500, "n/a"), (10, 580, "80.4")),
    ])
    assert found["citizenship"] is None
    assert pending == []


def test_safe_learning_environments_is_the_safe_and_caring_row():
    text = "Education Quality 78.1\nSafe Learning Environments  77.3 80.7 80.3\n"
    found = measures_from_text(text)
    assert found["safe_caring"] == 77.3


def test_sirr_link_is_a_results_report_and_a_fee_pdf_is_not():
    href = "/documents/abc/Harold_Panabaker-SIRR-24-25.pdf"
    assert is_results_report(href, "Harold Panabaker SIRR 24 25")
    assert is_results_report("/documents/abc/School-Improvement-Results-Report.pdf")
    assert not is_results_report("/documents/abc/Report-to-Parents-on-Fees-2024-2025.pdf", "Fees")
    assert not is_results_report("/documents/abc/Harold_Panabaker-SDP-25-26.pdf", "School Development Plan")
    html = f'<a href="{href}?fingerprint=1">Harold Panabaker SIRR 24 25</a>'
    urls = results_report_urls(html, "https://haroldpanabaker.cbe.ab.ca")
    assert urls == ["https://haroldpanabaker.cbe.ab.ca/documents/abc/Harold_Panabaker-SIRR-24-25.pdf"]
