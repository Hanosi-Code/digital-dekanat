from dekanat.core.extract.normalize import find_dates, normalize_course


def iso(t):
    return [d for _, d in find_dates(t)]


def test_date_formats_give_same_value():
    assert iso("01.09.2026") == ["2026-09-01"]
    assert iso("1 сентября 2026 года") == ["2026-09-01"]
    assert iso("1 сентября 2026 г.") == ["2026-09-01"]
    assert iso("2026-09-01") == ["2026-09-01"]
    assert iso("1/9/2026") == ["2026-09-01"]


def test_period_two_dates_in_order():
    assert iso("с 01.09.2022 по 30.06.2026") == ["2022-09-01", "2026-06-30"]
    assert iso("с 1 сентября 2022 года по 30 июня 2026 года") == ["2022-09-01", "2026-06-30"]


def test_ocr_letter_o_in_date():
    assert iso("О1.09.2026") == ["2026-09-01"]


def test_invalid_date_is_skipped():
    assert iso("31.02.2026") == []


def test_course():
    assert normalize_course("2 курс") == "2"
    assert normalize_course("II") == "2"
    assert normalize_course("третий") == "3"
