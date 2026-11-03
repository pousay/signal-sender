"""Signal parsing, entity preservation, and caption formatting."""

import re
from dataclasses import dataclass

MAX_CAPTION_LENGTH = 1024

ORDER_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*(buy\s*limit|sell\s*limit|buy\s*stop|sell\s*stop|buy|sell)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?)",
    re.MULTILINE,
)
STOP_LOSS_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*(?:stop\s*loss|stoploss|sl)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?|\[?مشاهده\]?(?:\([^)]+\))?)",
    re.MULTILINE,
)
TARGET_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*(?:target|tp)(?:\s*[0-9]+)?\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?)",
    re.MULTILINE,
)
STOP_LOSS_REPLACE_REGEX = re.compile(
    r"(?i)((?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*(?:stop\s*loss|stoploss|sl)\s*[:=\-]?\s*)([0-9]+(?:[.,][0-9]+)?|\[?مشاهده\]?(?:\([^)]+\))?)",
    re.MULTILINE,
)


class FormattingError(Exception):
    """Base exception for signal parsing and formatting."""


class SignalParseError(FormattingError):
    """Raised when required signal fields are missing, invalid, or ambiguous."""


class CaptionTooLongError(FormattingError):
    """Raised when the generated public caption exceeds Telegram limit."""


@dataclass
class ParsedSignal:
    """Structured representation of extracted signal values."""

    order_type: str
    entry_price: str
    stop_loss: str | None = None
    target: str | None = None
    stop_loss_match_span: tuple[int, int] | None = None

    @property
    def sell_limit(self) -> str:
        """Backward compatibility alias for entry_price."""
        return self.entry_price


def parse_signal_text(text: str) -> ParsedSignal:
    """Extract Buy/Sell order and optional Stop loss (and Target) values.

    Raises:
        SignalParseError: if Order field is missing, invalid, or ambiguous.
    """
    if not text or not text.strip():
        raise SignalParseError("Signal text is empty")

    norm_text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 1. Order (Buy stop, Buy limit, Sell stop, Sell limit, Buy, Sell)
    order_matches = list(ORDER_REGEX.finditer(norm_text))
    if not order_matches:
        raise SignalParseError("No valid order found in signal text")

    if len(order_matches) > 1:
        values = {m.group(2).replace(",", ".") for m in order_matches}
        if len(values) > 1:
            raise SignalParseError(
                "Ambiguous signal text containing multiple distinct order values"
            )

    primary_order = order_matches[0]
    raw_kw = re.sub(r"\s+", " ", primary_order.group(1).strip().lower())
    if "buy" in raw_kw:
        if "stop" in raw_kw:
            order_type = "Buy stop"
        elif "limit" in raw_kw:
            order_type = "Buy limit"
        else:
            order_type = "Buy"
    else:
        if "stop" in raw_kw:
            order_type = "Sell stop"
        elif "limit" in raw_kw:
            order_type = "Sell limit"
        else:
            order_type = "Sell"

    entry_price = primary_order.group(2).replace(",", ".")

    # 2. Stop loss (optional; can be numeric or existing 'مشاهده')
    sl_matches = list(STOP_LOSS_REGEX.finditer(norm_text))
    sl_val: str | None = None
    sl_span: tuple[int, int] | None = None

    if sl_matches:
        numeric_sl_values = {
            m.group(1).replace(",", ".")
            for m in sl_matches
            if re.match(r"^[0-9]+(?:[.,][0-9]+)?$", m.group(1).replace(",", "."))
        }
        if len(numeric_sl_values) > 1:
            raise SignalParseError(
                "Ambiguous signal text containing multiple distinct 'Stop loss' values"
            )

        primary_sl = sl_matches[0]
        raw_sl = primary_sl.group(1).replace(",", ".")
        if re.match(r"^[0-9]+(?:[.,][0-9]+)?$", raw_sl):
            sl_val = raw_sl
        sl_span = primary_sl.span(1)

    # 3. Target (optional)
    tp_match = TARGET_REGEX.search(norm_text)
    tp_val = tp_match.group(1).replace(",", ".") if tp_match else None

    return ParsedSignal(
        order_type=order_type,
        entry_price=entry_price,
        stop_loss=sl_val,
        target=tp_val,
        stop_loss_match_span=sl_span,
    )


def generate_public_caption(
    original_text: str,
    parsed: ParsedSignal,
    bot_username: str,
    signal_id: int,
) -> str:
    """Generate public channel caption by replacing Stop loss value with deep link.

    Replaces the Stop loss value with `[مشاهده](https://t.me/{bot_username}?start={signal_id})`
    while preserving the entry order, surrounding text, emojis, and hashtags.

    Raises:
        CaptionTooLongError: if final caption exceeds 1024 characters.
    """
    clean_bot = bot_username.lstrip("@")
    deep_link = f"https://t.me/{clean_bot}?start={signal_id}"
    view_link = f"[مشاهده]({deep_link})"

    norm_text = original_text.replace("\r\n", "\n").replace("\r", "\n")

    def _replace_sl(match: re.Match) -> str:
        prefix = match.group(1)
        return f"{prefix}{view_link}"

    caption, count = STOP_LOSS_REPLACE_REGEX.subn(_replace_sl, norm_text, count=1)
    if count == 0 and parsed.stop_loss is not None:
        raise SignalParseError("Failed to locate Stop loss value in signal text for replacement")

    if len(caption) > MAX_CAPTION_LENGTH:
        raise CaptionTooLongError(
            f"Caption length {len(caption)} exceeds Telegram limit of {MAX_CAPTION_LENGTH}"
        )

    return caption


def format_premium_signal_details(
    order_type: str | None = None,
    entry_price: str | None = None,
    stop_loss: str | None = None,
    target: str | None = None,
    sell_limit: str | None = None,
) -> str:
    """Format full real signal parameters for active premium members."""
    if not entry_price and sell_limit:
        entry_price = sell_limit
    if not order_type:
        order_type = "Sell limit"

    lines = []
    if entry_price:
        clean_label = order_type.strip(": ")
        lines.append(f"🔹 {clean_label}: {entry_price}")
    if stop_loss:
        lines.append(f"🔹 Stop loss: {stop_loss}")
    if target:
        lines.append(f"🔹 Target: {target}")
    return "\n".join(lines)
