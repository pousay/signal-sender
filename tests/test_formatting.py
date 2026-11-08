"""Tests for signal parsing and caption formatting."""

import pytest

from app.utils.formatting import (
    CaptionTooLongError,
    SignalParseError,
    format_premium_signal_details,
    generate_public_caption,
    parse_signal_text,
)


def test_parse_valid_sell_signal_text():
    raw = (
        "🔴 سیگنال فروش طلا #XAUUSD\n"
        "🔹 Sell limit: 77950\n"
        "🔹 Stop loss: 78650\n"
        "🔹 Target: 76900\n"
        "مدیریت سرمایه رعایت شود."
    )
    parsed = parse_signal_text(raw)
    assert parsed.order_type == "Sell limit"
    assert parsed.entry_price == "77950"
    assert parsed.sell_limit == "77950"
    assert parsed.stop_loss == "78650"
    assert parsed.target == "76900"


def test_parse_valid_buy_signal_text():
    raw = (
        "🟢 سیگنال خرید اتریوم | ETH/USDT\n\n"
        "🔹 Buy limit: 2230 \n"
        "🔹 Stop loss: 2198 \n"
        "🔹 Target: 2287 \n"
        "⚖️ RR: بزرگتر از یک\n"
        "⏰ M15.H1"
    )
    parsed = parse_signal_text(raw)
    assert parsed.order_type == "Buy limit"
    assert parsed.entry_price == "2230"
    assert parsed.sell_limit == "2230"
    assert parsed.stop_loss == "2198"
    assert parsed.target == "2287"


def test_parse_case_insensitivity_and_shorthand():
    # UPPERCASE SELL
    raw_upper_sell = "🔻 SELL LIMIT: 50000\n▫️ STOP LOSS: 51000\n▫️ TARGET: 48000"
    parsed_upper_sell = parse_signal_text(raw_upper_sell)
    assert parsed_upper_sell.order_type == "Sell limit"
    assert parsed_upper_sell.entry_price == "50000"
    assert parsed_upper_sell.stop_loss == "51000"
    assert parsed_upper_sell.target == "48000"

    # lowercase buy and shorthand sl/tp
    raw_shorthand_buy = "buy: 1200\nsl: 1150\ntp: 1300"
    parsed_shorthand_buy = parse_signal_text(raw_shorthand_buy)
    assert parsed_shorthand_buy.order_type == "Buy"
    assert parsed_shorthand_buy.entry_price == "1200"
    assert parsed_shorthand_buy.stop_loss == "1150"
    assert parsed_shorthand_buy.target == "1300"

    # Mixed case Sell and SL
    raw_mixed = "🔹 sell limit = 1.2345 \n🔹 SL: 1.2300\n🔹 TP 1: 1.2400"
    parsed_mixed = parse_signal_text(raw_mixed)
    assert parsed_mixed.order_type == "Sell limit"
    assert parsed_mixed.entry_price == "1.2345"
    assert parsed_mixed.stop_loss == "1.2300"
    assert parsed_mixed.target == "1.2400"


def test_parse_missing_order():
    raw = "Stop loss: 49000\nTarget: 51000"
    with pytest.raises(SignalParseError) as exc:
        parse_signal_text(raw)
    assert "No valid order found" in str(exc.value)


def test_parse_optional_stop_loss():
    raw = "Buy limit: 50000\nTarget: 51000"
    parsed = parse_signal_text(raw)
    assert parsed.order_type == "Buy limit"
    assert parsed.entry_price == "50000"
    assert parsed.stop_loss is None
    assert parsed.target == "51000"


def test_parse_all_six_order_types():
    cases = [
        ("Buy stop: 100\nSL: 90", "Buy stop", "100"),
        ("Buy limit: 100\nSL: 90", "Buy limit", "100"),
        ("Sell stop: 100\nSL: 110", "Sell stop", "100"),
        ("Sell limit: 100\nSL: 110", "Sell limit", "100"),
        ("Buy: 100\nSL: 90", "Buy", "100"),
        ("Sell: 100\nSL: 110", "Sell", "100"),
    ]
    for text, expected_type, expected_price in cases:
        parsed = parse_signal_text(text)
        assert parsed.order_type == expected_type
        assert parsed.entry_price == expected_price


def test_parse_mosen_sample_with_view_stop_loss():
    raw = (
        "فروش دلار/فرانک سوئیس | USD/CHF\n\n"
        "🔹 Sell limit : 0.82030\n"
        "🔹 Stop loss: مشاهده\n"
        "🔹 Target: 0.81470 (56 pip)\n"
        "⚖️ Risk/Reward: بین 1 الی 2\n"
        "⏰ M15.H1\n"
        "📊Price Now ~ 0.8185\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔍 دلیل ورود :\n"
        "فرانک سوئیس قوی‌ترین ارز بازار امروز است\n"
        "@app_farex"
    )
    parsed = parse_signal_text(raw)
    assert parsed.order_type == "Sell limit"
    assert parsed.entry_price == "0.82030"
    assert parsed.stop_loss is None
    assert parsed.target == "0.81470"

    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_RoBot",
        signal_id=42,
    )
    assert "⚫️ Stop loss: [مشاهده](https://t.me/Farex_RoBot?start=42)" in caption
    assert "🔴 Sell limit : 0.82030" in caption


def test_parse_forwarded_post_with_existing_markdown_link():
    raw = (
        "فروش دلار/فرانک سوئیس | USD/CHF\n\n"
        "🔹 Sell limit : 0.82030\n"
        "🔹 Stop loss: [مشاهده](https://t.me/Farex_RoBot?start=10)\n"
        "🔹 Target: 0.81470 (56 pip)\n"
    )
    parsed = parse_signal_text(raw)
    assert parsed.order_type == "Sell limit"
    assert parsed.entry_price == "0.82030"
    assert parsed.stop_loss is None

    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_RoBot",
        signal_id=99,
    )
    assert "⚫️ Stop loss: [مشاهده](https://t.me/Farex_RoBot?start=99)" in caption


def test_parse_and_caption_multiple_targets():
    raw = (
        "🔵 سیگنال خرید دلار فرانک | USD/CHF\n\n"
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢Target 1: 0.81900\n"
        "🟢Target 2: 0.82200\n"
    )
    parsed = parse_signal_text(raw)
    assert parsed.order_type == "Buy limit"
    assert parsed.entry_price == "0.81630"
    assert parsed.stop_loss == "0.81200"
    assert len(parsed.targets) == 2
    assert parsed.targets[0] == ("Target 1", "0.81900")
    assert parsed.targets[1] == ("Target 2", "0.82200")

    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=50,
    )
    assert "⚫️ Stop loss: [مشاهده](https://t.me/Farex_Robot?start=50)" in caption
    assert "🟢 Target 1: [مشاهده](https://t.me/Farex_Robot?start=50)" in caption
    assert "🟢 Target 2: [مشاهده](https://t.me/Farex_Robot?start=50)" in caption


def test_parse_ambiguous_multiple_orders():
    raw = "Sell limit: 1000\nBuy limit: 2000\nStop loss: 900"
    with pytest.raises(SignalParseError) as exc:
        parse_signal_text(raw)
    assert "Ambiguous signal text" in str(exc.value)


def test_parse_ambiguous_multiple_stop_loss():
    raw = "Sell limit: 1000\nStop loss: 1100\nSL: 1200"
    with pytest.raises(SignalParseError) as exc:
        parse_signal_text(raw)
    assert "Ambiguous signal text containing multiple distinct 'Stop loss' values" in str(
        exc.value
    )


def test_generate_public_caption_hides_stop_loss_and_keeps_order_price():
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
        "🔴 Sell limit: 77950\n"
        "⚫️ Stop loss: [مشاهده](https://t.me/my_signal_bot?start=175)\n"
        "🟢 Target: [مشاهده](https://t.me/my_signal_bot?start=175)\n"
        "موفق باشید 🌹"
    )
    assert caption == expected


def test_generate_public_caption_buy_signal():
    raw = (
        "🟢 سیگنال خرید اتریوم | ETH/USDT\n\n"
        "🔹 Buy limit: 2230 \n"
        "🔹 Stop loss: 2198 \n"
        "🔹 Target: 2287 \n"
        "⚖️ RR: بزرگتر از یک\n"
        "⏰ M15.H1"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=4,
    )

    expected = (
        "🔵 سیگنال خرید اتریوم | ETH/USDT\n\n"
        "🔵 Buy limit: 2230 \n"
        "⚫️ Stop loss: [مشاهده](https://t.me/Farex_Robot?start=4) \n"
        "🟢 Target: [مشاهده](https://t.me/Farex_Robot?start=4) \n"
        "⚖️ RR: بزرگتر از یک\n"
        "⏰ M15.H1"
    )
    assert caption == expected


def test_generate_public_caption_crlf_input():
    raw = "Sell limit: 100\r\nStop loss: 110\r\nTarget: 90\r\n"
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="test_bot",
        signal_id=10,
    )
    expected = (
        "🔴 Sell limit: 100\n"
        "⚫️ Stop loss: [مشاهده](https://t.me/test_bot?start=10)\n"
        "🟢 Target: [مشاهده](https://t.me/test_bot?start=10)\n"
    )
    assert caption == expected


def test_generate_public_caption_user_sample_sell_bitcoin():
    raw = (
        "🔴 سیگنال فروش بیت‌کوین | BTC/USDT\n\n"
        "🔹 Sell limit: 77950\n"
        "🔹 Stop loss: 78650\n"
        "🔹 Target: 76900\n"
        "⚖️ RR: یک به 1.5\n"
        "⏰ M15.H1\n"
        "✅Eatebar Pending :  امروز \n"
        "━━━━━━━━━━━━━━\n\n"
        "🔍 دلیل ورود تکنیکالی:\n"
        "۱. ساختار نزولی بازار: روند غالب در تایم‌فریم‌های بالاتر نزولی است و "
        "ساختار سقف‌ها و کف‌های پایین‌تر، برتری فروشندگان را نشان می‌دهد.\n\n"
        "۲. محدوده مقاومتی: قیمت در حال اصلاح صعودی به سمت محدوده مقاومتی 77950 است؛ "
        "این ناحیه می‌تواند محل بازگشت فشار فروش باشد.\n\n"
        "#بیت_کوین #سیگنال_معاملاتی\n\n"
        "@app_Farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=4,
    )
    assert "🔴 Sell limit: 77950" in caption
    assert "⚫️ Stop loss: [مشاهده](https://t.me/Farex_Robot?start=4)" in caption
    assert "🟢 Target: [مشاهده](https://t.me/Farex_Robot?start=4)" in caption
    assert "قیمت در حال اصلاح صعودی به سمت محدوده مقاومتی 77950 است" in caption


def test_generate_public_caption_too_long():
    long_text = "Sell limit: 100\nStop loss: 110\n" + ("A" * 1020)
    parsed = parse_signal_text(long_text)
    with pytest.raises(CaptionTooLongError):
        generate_public_caption(
            original_text=long_text,
            parsed=parsed,
            bot_username="bot",
            signal_id=1,
        )


def test_format_premium_signal_details():
    formatted_sell = format_premium_signal_details(
        order_type="Sell limit",
        entry_price="77950",
        stop_loss="78650",
        target="76900",
    )
    assert (
        formatted_sell
        == "🔴 Sell limit: 77950\n⚫️ Stop loss: 78650\n🟢 Target: 76900"
    )

    formatted_buy = format_premium_signal_details(
        order_type="Buy limit",
        entry_price="2230",
        stop_loss="2198",
        target="2287",
    )
    assert (
        formatted_buy
        == "🔵 Buy limit: 2230\n⚫️ Stop loss: 2198\n🟢 Target: 2287"
    )

    formatted_multiple_targets = format_premium_signal_details(
        order_type="Buy limit",
        entry_price="0.81630",
        stop_loss="0.81200",
        targets=[("Target 1", "0.81900"), ("Target 2", "0.82200")],
    )
    assert formatted_multiple_targets == (
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢 Target 1: 0.81900\n"
        "🟢 Target 2: 0.82200"
    )

    formatted_legacy = format_premium_signal_details(
        sell_limit="77950",
        stop_loss="78650",
        target="76900",
    )
    assert (
        formatted_legacy
        == "🔴 Sell limit: 77950\n⚫️ Stop loss: 78650\n🟢 Target: 76900"
    )
