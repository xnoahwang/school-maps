"""School-name folding used to match a City row to an Alberta PAT row.

Does not read the spreadsheet. Names that still differ after folding stay
unmatched; the matcher does not guess a nearby school.
"""
from build_data import normalize_name


def test_empty_name_is_blank():
    assert normalize_name("") == ""
    assert normalize_name(None) == ""


def test_identical_names_match():
    assert normalize_name("West Dalhousie School") == normalize_name("West Dalhousie School")


def test_filler_saint_and_ampersand_match():
    assert normalize_name("The Briar Hill School") == normalize_name("Briar Hill")
    assert normalize_name("St. Mary's School") == normalize_name("Saint Mary's")
    assert normalize_name("A & B School") == normalize_name("A and B")


def test_different_names_do_not_match():
    assert normalize_name("Briar Hill") != normalize_name("Rundle")
    # "st." is rewritten only when a space follows, so a stuck abbreviation stays different.
    assert normalize_name("St.Mary") != normalize_name("Saint Mary")
