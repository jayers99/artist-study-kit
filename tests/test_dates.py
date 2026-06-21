from scripts.dates import parse_year


def test_parse_year_plain():
    assert parse_year("1889") == 1889


def test_parse_year_circa():
    assert parse_year("c. 1889") == 1889
    assert parse_year("circa 1880s") == 1880


def test_parse_year_range_takes_start():
    assert parse_year("1889–90") == 1889
    assert parse_year("1889-1890") == 1889


def test_parse_year_month_prefix():
    assert parse_year("May 1889") == 1889


def test_parse_year_unknown_is_none():
    assert parse_year("") is None
    assert parse_year("n.d.") is None
    assert parse_year("oil on canvas") is None
