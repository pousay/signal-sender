"""Tests for signal parsing and caption formatting."""

import pytest

from app.utils.formatting import (
    CaptionTooLongError,
    SignalParseError,
    format_premium_signal_details,
    generate_public_caption,
    parse_signal_text,
    to_persian_numbers,
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
    assert parsed.stop_loss == "مشاهده"
    assert parsed.target == "0.81470"

    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_RoBot",
        signal_id=42,
    )
    assert '⚫️ Stop loss: <a href="https://t.me/Farex_RoBot?start=42">مشاهده</a>' in caption
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
    assert parsed.stop_loss == "مشاهده"
    assert parsed.target == "0.81470"

    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_RoBot",
        signal_id=99,
    )
    assert '⚫️ Stop loss: <a href="https://t.me/Farex_RoBot?start=99">مشاهده</a>' in caption


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
    assert '⚫️ Stop loss: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption
    assert '🟢 Target 1: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption
    assert '🟢 Target 2: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption


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
        '⚫️ Stop loss: <a href="https://t.me/my_signal_bot?start=175">مشاهده</a>\n'
        '🟢 Target: <a href="https://t.me/my_signal_bot?start=175">مشاهده</a>\n'
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
        risk_reward="1.30",
    )

    expected = (
        "🔵 سیگنال خرید اتریوم | ETH/USDT\n\n"
        "🔵 Buy limit: 2230 \n"
        '⚫️ Stop loss: <a href="https://t.me/Farex_Robot?start=4">مشاهده</a> \n'
        '🟢 Target: <a href="https://t.me/Farex_Robot?start=4">مشاهده</a> \n'
        "⚖️ Risk/Reward : 1.30\n"
        "⏰ M15.H1"
    )
    assert caption == expected


def test_generate_public_caption_standardizes_risk_reward():
    raw = (
        "🔵 سیگنال خرید دلار فرانک | USD/CHF\n\n"
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢 Target: 0.82000\n"
        "⚖️ Risk/Riward : 1.30\n"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=50,
        risk_reward="بین 1 الی 2",
    )
    assert "⚖️ Risk/Reward : بین 1 الی 2" in caption


def test_full_signal_format_v2_end_to_end():
    raw_user_sample = (
        "🔵 سیگنال خرید دلار فرانک | USD/CHF\n\n"
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢Target 1: 0.81900\n"
        "🟢Target 2: 0.82200\n"
        "⚖️ Risk/Riward : 1.30\n"
        "⏰ M15.H1\n"
        "📊 Price Now ~ 0.81440 (💥19 پیپ تا فعال شدن💥)\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔍 دلیل ورود :\n"
        "روند غالب نزولی و پرقدرت است.\n\n"
        "#دلار_فرانک #سیگنال_معاملاتی\n"
        "کد : 14050725\n"
        "🆔 @app_farex\n"
        "👤 @orginal"
    )

    parsed = parse_signal_text(raw_user_sample)
    assert parsed.order_type == "Buy limit"
    assert parsed.entry_price == "0.81630"
    assert parsed.stop_loss == "0.81200"
    assert len(parsed.targets) == 2
    assert parsed.targets[0] == ("Target 1", "0.81900")
    assert parsed.targets[1] == ("Target 2", "0.82200")

    caption = generate_public_caption(
        original_text=raw_user_sample,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=50,
        timestamp=1762621772,
        risk_reward="1.30",
    )

    assert "🔵 سیگنال خرید دلار فرانک | USD/CHF" in caption
    assert "🔵 Buy limit: 0.81630" in caption
    assert '⚫️ Stop loss: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption
    assert '🟢 Target 1: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption
    assert '🟢 Target 2: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption
    assert "⚖️ Risk/Reward : 1.30" in caption
    assert '📊 <tg-time unix="1762621772">Price Now</tg-time> ~ 0.81440' in caption
    assert "#دلار_فرانک #سیگنال_معاملاتی" in caption
    assert "🆔 @app_farex" in caption

    premium_details = format_premium_signal_details(
        order_type=parsed.order_type,
        entry_price=parsed.entry_price,
        stop_loss=parsed.stop_loss,
        targets=parsed.targets,
    )
    assert "🔵 Buy limit: `0.81630`" in premium_details
    assert "⚫️ Stop loss: `0.81200`" in premium_details
    assert "🟢 Target 1: `0.81900`" in premium_details
    assert "🟢 Target 2: `0.82200`" in premium_details


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
        '⚫️ Stop loss: <a href="https://t.me/test_bot?start=10">مشاهده</a>\n'
        '🟢 Target: <a href="https://t.me/test_bot?start=10">مشاهده</a>\n'
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
    assert '⚫️ Stop loss: <a href="https://t.me/Farex_Robot?start=4">مشاهده</a>' in caption
    assert '🟢 Target: <a href="https://t.me/Farex_Robot?start=4">مشاهده</a>' in caption
    assert "قیمت در حال اصلاح صعودی به سمت محدوده مقاومتی 77950 است" in caption


def test_generate_public_caption_price_now_timestamp_link():
    raw = (
        "🔵 سیگنال خرید دلار فرانک | USD/CHF\n\n"
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢 Target: 0.82000\n"
        "📊 Price Now ~ 0.81440 (💥19 پیپ تا فعال شدن💥)\n"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=50,
        timestamp=1762621772,
    )
    assert '📊 <tg-time unix="1762621772">Price Now</tg-time> ~ 0.81440' in caption


def test_generate_public_caption_replaces_existing_daily_code():
    raw = (
        "🔵 سیگنال خرید طلا\n"
        "🔵 Buy limit: 2000\n"
        "⚫️ Stop loss: 1990\n"
        "کد : 14050725\n"
        "🆔 @app_farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=1,
        daily_code="140508171",
    )
    assert "کد : ۱۴۰۵۰۸۱۷۱" in caption
    assert "14050725" not in caption


def test_generate_public_caption_inserts_daily_code_before_footer():
    raw = (
        "🔵 سیگنال خرید طلا\n"
        "🔵 Buy limit: 2000\n"
        "⚫️ Stop loss: 1990\n"
        "#طلا\n"
        "@app_farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=1,
        daily_code="140508172",
    )
    assert "کد : ۱۴۰۵۰۸۱۷۲\n🆔 @app_farex\n👤 @orginal" in caption


def test_generate_public_caption_appends_daily_code_when_no_footer():
    raw = (
        "🔵 سیگنال خرید طلا\n"
        "🔵 Buy limit: 2000\n"
        "⚫️ Stop loss: 1990\n"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=1,
        daily_code="140508173",
    )
    assert caption.endswith("کد : ۱۴۰۵۰۸۱۷۳\n")


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
        == "🔴 Sell limit: `77950`\n⚫️ Stop loss: `78650`\n🟢 Target: `76900`"
    )

    formatted_buy = format_premium_signal_details(
        order_type="Buy limit",
        entry_price="2230",
        stop_loss="2198",
        target="2287",
    )
    assert (
        formatted_buy
        == "🔵 Buy limit: `2230`\n⚫️ Stop loss: `2198`\n🟢 Target: `2287`"
    )

    formatted_multiple_targets = format_premium_signal_details(
        order_type="Buy limit",
        entry_price="0.81630",
        stop_loss="0.81200",
        targets=[("Target 1", "0.81900"), ("Target 2", "0.82200")],
        value="0.17لات",
    )
    assert formatted_multiple_targets == (
        "🔵 Buy limit: `0.81630`\n"
        "⚫️ Stop loss: `0.81200`\n"
        "🟢 Target 1: `0.81900`\n"
        "🟢 Target 2: `0.82200`\n"
        "🗻 value: `0.17`لات"
    )

    formatted_legacy = format_premium_signal_details(
        sell_limit="77950",
        stop_loss="78650",
        target="76900",
    )
    assert (
        formatted_legacy
        == "🔴 Sell limit: `77950`\n⚫️ Stop loss: `78650`\n🟢 Target: `76900`"
    )


def test_parse_signal_text_with_value_field():
    raw_with_emoji = (
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢 Target: 0.82000\n"
        "🗻 value: 0.17لات\n"
    )
    parsed = parse_signal_text(raw_with_emoji)
    assert parsed.value == "0.17لات"

    raw_without_emoji = (
        "Sell limit: 1.2345\n"
        "SL: 1.2400\n"
        "TP: 1.2200\n"
        "value: 0.50\n"
    )
    parsed_plain = parse_signal_text(raw_without_emoji)
    assert parsed_plain.value == "0.50"


def test_generate_public_caption_strips_value_line():
    raw = (
        "🔵 سیگنال خرید دلار فرانک | USD/CHF\n\n"
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢 Target 1: 0.81900\n"
        "🟢 Target 2: 0.82200\n"
        "⚖️ Risk/Riward : 1.30\n"
        "🗻 value: 0.17لات\n"
        "⏰ M15.H1\n"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=50,
        risk_reward="1.30",
    )
    assert "value" not in caption
    assert "0.17لات" not in caption
    assert "🗻" not in caption
    assert "🔵 Buy limit: 0.81630" in caption
    assert '⚫️ Stop loss: <a href="https://t.me/Farex_Robot?start=50">مشاهده</a>' in caption
    assert "⏰ M15.H1" in caption


def test_format_premium_signal_details_copiable_mono_and_value():
    details = format_premium_signal_details(
        order_type="Buy limit",
        entry_price="0.81630",
        stop_loss="94646",
        targets=[("Target 1", "94646"), ("Target 2", "31551")],
        value="0.17لات",
    )
    expected = (
        "🔵 Buy limit: `0.81630`\n"
        "⚫️ Stop loss: `94646`\n"
        "🟢 Target 1: `94646`\n"
        "🟢 Target 2: `31551`\n"
        "🗻 value: `0.17`لات"
    )
    assert details == expected


def test_footer_standardization_replaces_single_channel_handle():
    raw = (
        "🔴 سیگنال فروش انس طلا\n"
        "🔹 Sell limit: 2650.50\n"
        "🔹 Stop loss: 2660.00\n"
        "@app_farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=10,
    )
    assert caption.endswith("🆔 @app_farex\n👤 @orginal")


def test_footer_standardization_replaces_reversed_or_partial_handles():
    raw = (
        "🔵 سیگنال خرید جفت ارز\n"
        "🔹 Buy limit: 1.0850\n"
        "🔹 Stop loss: 1.0800\n"
        "👤 @orginal\n"
        "🆔 @app_Farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=11,
    )
    assert caption.endswith("🆔 @app_farex\n👤 @orginal")


def test_static_risk_reward_defaults_to_persian_phrase():
    raw = (
        "🔵 سیگنال خرید طلا\n"
        "🔵 Buy limit: 2640.00\n"
        "⚫️ Stop loss: 2630.00\n"
        "🟢 Target: 2660.00\n"
        "⚖️ Risk/Riward : 1.30\n"
        "@app_farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=12,
        risk_reward=None,
    )
    assert "⚖️ Risk/Reward : بین 1 الی 2" in caption


def test_to_persian_numbers_conversion():
    assert to_persian_numbers("14050725") == "۱۴۰۵۰۷۲۵"
    assert to_persian_numbers("140508171") == "۱۴۰۵۰۸۱۷۱"
    assert to_persian_numbers("0123456789") == "۰۱۲۳۴۵۶۷۸۹"


def test_persian_code_in_caption_preserves_latin_signal_numbers():
    raw = (
        "🔵 سیگنال خرید دلار فرانک | USD/CHF\n"
        "🔵 Buy limit: 0.81630\n"
        "⚫️ Stop loss: 0.81200\n"
        "🟢 Target 1: 0.81900\n"
        "⚖️ Risk/Riward : 1.30\n"
        "📊 Price Now ~ 0.81440\n"
        "#دلار_فرانک #سیگنال_معاملاتی\n"
        "کد : 14050725\n"
        "@app_farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=15,
        daily_code="140508175",
    )
    # Daily code rendered with Persian digits
    assert "کد : ۱۴۰۵۰۸۱۷۵" in caption
    assert "14050725" not in caption
    assert "140508175" not in caption
    # Prices and parameters remain Latin digits
    assert "0.81630" in caption
    assert "0.81440" in caption
    # Footer standardized
    assert caption.endswith("🆔 @app_farex\n👤 @orginal")
    # Static RR applied
    assert "⚖️ Risk/Reward : بین 1 الی 2" in caption


def test_persian_code_conversion_when_daily_code_not_passed():
    raw = (
        "🔵 سیگنال خرید یورو | EUR/USD\n"
        "🔵 Buy limit: 1.0850\n"
        "⚫️ Stop loss: 1.0800\n"
        "کد : 14050725\n"
        "@app_farex"
    )
    parsed = parse_signal_text(raw)
    caption = generate_public_caption(
        original_text=raw,
        parsed=parsed,
        bot_username="Farex_Robot",
        signal_id=16,
        daily_code=None,
    )
    assert "کد : ۱۴۰۵۰۷۲۵" in caption
    assert "14050725" not in caption
    assert "1.0850" in caption

