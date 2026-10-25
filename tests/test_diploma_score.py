"""Diploma exam rates for the high-school list.

The page ranks a senior school on the newest year of exam marks, not on the
school-awarded mark. These tests do not download the workbook.
"""

import pandas as pd

from build_data import diploma_latest_by_school, school_score


def _frame(rows):
    return pd.DataFrame(rows)


def test_empty_frame_returns_no_schools():
    assert diploma_latest_by_school(_frame([])) == {}


def test_newest_year_averages_exam_marks_and_skips_suppressed_cells():
    frame = _frame([
        {
            "Diploma Course": "English Lang Arts 30-1",
            "Authority Name": "The Calgary School Division",
            "School Code": "1",
            "School Name": "Example School",
            "2024 Sch Exam Mark % Acc": "90",
            "2024 Sch Exam Mark % Exc": "30",
            "2025 Sch Exam Mark % Acc": "80",
            "2025 Sch Exam Mark % Exc": "20",
        },
        {
            "Diploma Course": "Mathematics 30-1",
            "Authority Name": "The Calgary School Division",
            "School Code": "1",
            "School Name": "Example School",
            "2024 Sch Exam Mark % Acc": "10",
            "2024 Sch Exam Mark % Exc": "10",
            "2025 Sch Exam Mark % Acc": "n/a",
            "2025 Sch Exam Mark % Exc": "n/a",
        },
        {
            "Diploma Course": "1. Due to the COVID-19 pandemic, ignore this row.",
            "Authority Name": "The Calgary School Division",
            "School Code": "1",
            "School Name": "Example School",
            "2025 Sch Exam Mark % Acc": "1",
            "2025 Sch Exam Mark % Exc": "1",
        },
    ])
    result = diploma_latest_by_school(frame)
    block = result[("The Calgary School Division", "example")]["diploma_latest"]
    assert block == {"acc": 80.0, "exc": 20.0, "years": [2025], "year": 2025}
    assert school_score(block) == 50.0


def test_a_school_with_no_published_rate_is_omitted():
    frame = _frame([{
        "Diploma Course": "Biology 30",
        "Authority Name": "The Calgary School Division",
        "School Code": "2",
        "School Name": "No Result School",
        "2025 Sch Exam Mark % Acc": "n/a",
        "2025 Sch Exam Mark % Exc": "n/a",
    }])
    assert diploma_latest_by_school(frame) == {}
