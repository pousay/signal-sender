"""Tests for signal parsing and caption formatting."""

import pytest

from app.utils.formatting import (
    CaptionTooLongError,
    SignalParseError,
    format_premium_signal_details,
    generate_public_caption,
    parse_signal_text,
)


def test_parse_valid_signal_text():
    raw = (
        "🔴 سیگنال فروش طلا #XAUUSD\n"
        "🔹 Sell limit: 77950\n"
        "🔹 Stop loss: 78650\n"
        "🔹 Target: 76900\n"
        "مدیریت سرمایه رعایت شود."
    )
    parsed = parse_signal_text(raw)
    assert parsed.sell_limit == "77950"
    assert parsed.stop_loss == "78650"
    assert parsed.target == "76900"


def test_parse_decimal_and_variations():
    raw = "🔹 sell limit = 1.2345 \n🔹 SL: 1.2300\n🔹 TP 1: 1.2400"
    parsed = parse_signal_text(raw)
    assert parsed.sell_limit == "1.2345"
    assert parsed.stop_loss == "1.2300"
    assert parsed.target == "1.2400"


def test_parse_missing_sell_limit():
    raw = "Buy limit: 50000\nStop loss: 49000"
    with pytest.raises(SignalParseError) as exc:
        parse_signal_text(raw)
    assert "No valid 'Sell limit' found" in str(exc.value)


def test_parse_ambiguous_multiple_sell_limits():
    raw = "Sell limit: 1000\nSell limit: 2000"
    with pytest.raises(SignalParseError) as exc:
        parse_signal_text(raw)
    assert "Ambiguous signal text" in str(exc.value)


def test_generate_public_caption_replaces_only_sell_limit_value():
    raw = (
        "🔴 سیگنال فروش طلا #XAUUSD\n"
        "🔹 Sell limit: 77950\n"
        "🔹 Stop loss: 78650\n"
        "🔹 Target: 76900\n"
        "موفق باشید 🌹"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="my_signal_bot",
        signal_id=175,
    )

    expected = (
        "🔴 سیگنال فروش طلا #XAUUSD\n"
        "🔹 Sell limit: [مشاهده](https://t.me/my_signal_bot?start=175)\n"
        "🔹 Stop loss: 78650\n"
        "🔹 Target: 76900\n"
        "موفق باشید 🌹"
    )
    assert caption == expected


def test_generate_public_caption_too_long():
    long_text = "Sell limit: 100\n" + ("A" * 1020)
    parsed = parse_signal_text(long_text)
    with pytest.raises(CaptionTooLongError):
        generate_public_caption(
            original_text=long_text,
            parsed=parsed,
            bot_username="bot",
            signal_id=1,
        )


def test_format_premium_signal_details():
    formatted = format_premium_signal_details(
        sell_limit="77950",
        stop_loss="78650",
        target="76900",
    )
    assert (
        formatted
        == "🔹 Sell limit: 77950\n🔹 Stop loss: 78650\n🔹 Target: 76900"
    )
