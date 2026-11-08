"""Standalone Gregorian to Solar Hijri (Jalali) date conversion utilities."""

from datetime import datetime, timezone


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Convert a Gregorian calendar date to a Solar Hijri (Jalali) date.

    Args:
        gy: Gregorian year (e.g. 2026)
        gm: Gregorian month (1-12)
        gd: Gregorian day (1-31)

    Returns:
        tuple[int, int, int]: (jy, jm, jd) - Jalali year, month, and day.
    """
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy if gm > 2 else gy - 1
    days = (
        365 * gy
        + (gy2 + 4) // 4
        - (gy2 + 100) // 100
        + (gy2 + 400) // 400
        - 80
        + gd
        + g_d_m[gm - 1]
    )
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30

    return jy, jm, jd


def get_jalali_date_str(dt: datetime | None = None) -> str:
    """Format the given or current UTC date as an 8-digit Jalali string (YYYYMMDD).

    Args:
        dt: Optional datetime object. Defaults to datetime.now(timezone.utc).

    Returns:
        str: 8-digit string like '14050817'.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}{jm:02d}{jd:02d}"
