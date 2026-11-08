"""Tests for Gregorian to Jalali date conversions."""

from datetime import datetime, timezone

from app.utils.jalali import get_jalali_date_str, gregorian_to_jalali


def test_gregorian_to_jalali_standard_dates():
    # User target date: November 8, 2026 -> 1405-08-17
    assert gregorian_to_jalali(2026, 11, 8) == (1405, 8, 17)
    assert get_jalali_date_str(datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)) == "14050817"

    # Nowruz 1405: March 21, 2026 -> 1405-01-01
    assert gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)
    assert get_jalali_date_str(datetime(2026, 3, 21, tzinfo=timezone.utc)) == "14050101"

    # Last day of 1404: March 20, 2026 -> 1404-12-29
    assert gregorian_to_jalali(2026, 3, 20) == (1404, 12, 29)

    # Farvardin 31 vs Ordibehesht 1
    assert gregorian_to_jalali(2026, 4, 20) == (1405, 1, 31)
    assert gregorian_to_jalali(2026, 4, 21) == (1405, 2, 1)


def test_get_jalali_date_str_default_now():
    date_str = get_jalali_date_str()
    assert len(date_str) == 8
    assert date_str.isdigit()
