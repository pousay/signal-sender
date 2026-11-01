"""Signal parsing, entity preservation, and caption formatting."""

import re
from dataclasses import dataclass

MAX_CAPTION_LENGTH = 1024

SELL_LIMIT_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔸|▫️|\*|-)?\s*(?:sell\s*limit)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?)",
    re.MULTILINE,
)
STOP_LOSS_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔸|▫️|\*|-)?\s*(?:stop\s*loss|sl)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?)",
    re.MULTILINE,
)
TARGET_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔸|▫️|\*|-)?\s*(?:target|tp)(?:\s*[0-9]+)?\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?)",
    re.MULTILINE,
)


class FormattingError(Exception):
    """Base exception for signal parsing and formatting."""


class SignalParseError(FormattingError):
    """Raised when Sell limit field is missing, invalid, or ambiguous."""


class CaptionTooLongError(FormattingError):
    """Raised when the generated public caption exceeds Telegram limit."""


@dataclass
class ParsedSignal:
    """Structured representation of extracted signal values."""

    sell_limit: str
    stop_loss: str | None = None
    target: str | None = None
    sell_limit_match_span: tuple[int, int] | None = None


def parse_signal_text(text: str) -> ParsedSignal:
    """Extract Sell limit and optional Stop loss/Target values from raw signal text.

    Raises:
        SignalParseError: if Sell limit is missing, invalid, or ambiguous.
    """
    if not text or not text.strip():
        raise SignalParseError("Signal text is empty")

    matches = list(SELL_LIMIT_REGEX.finditer(text))
    if not matches:
        raise SignalParseError("No valid 'Sell limit' found in signal text")

    if len(matches) > 1:
        # Check if they report different values (ambiguity)
        values = {m.group(1).replace(",", ".") for m in matches}
        if len(values) > 1:
            raise SignalParseError(
                "Ambiguous signal text containing multiple distinct 'Sell limit' values"
            )

    primary_match = matches[0]
    sell_limit_val = primary_match.group(1).replace(",", ".")
    # Span of only the numeric value inside group(1)
    val_span = primary_match.span(1)

    # Optional Stop loss and Target extraction for private premium display
    sl_match = STOP_LOSS_REGEX.search(text)
    sl_val = sl_match.group(1).replace(",", ".") if sl_match else None

    tp_match = TARGET_REGEX.search(text)
    tp_val = tp_match.group(1).replace(",", ".") if tp_match else None

    return ParsedSignal(
        sell_limit=sell_limit_val,
        stop_loss=sl_val,
        target=tp_val,
        sell_limit_match_span=val_span,
    )


def generate_public_caption(
    original_text: str,
    parsed: ParsedSignal,
    bot_username: str,
    signal_id: int,
) -> str:
    """Generate public channel caption by replacing ONLY the Sell limit numeric value.

    Replaces the numeric span with `[مشاهده](https://t.me/{bot_username}?start={signal_id})`
    while preserving all surrounding text, line breaks, emojis, and hashtags.

    Raises:
        CaptionTooLongError: if final caption exceeds 1024 characters.
    """
    clean_bot = bot_username.lstrip("@")
    deep_link = f"https://t.me/{clean_bot}?start={signal_id}"
    view_link = f"[مشاهده]({deep_link})"

    if parsed.sell_limit_match_span is None:
        raise SignalParseError("Cannot generate caption without exact match span")

    start_idx, end_idx = parsed.sell_limit_match_span
    # Replace ONLY the exact numeric value span
    caption = original_text[:start_idx] + view_link + original_text[end_idx:]

    if len(caption) > MAX_CAPTION_LENGTH:
        raise CaptionTooLongError(
            f"Caption length {len(caption)} exceeds Telegram limit of {MAX_CAPTION_LENGTH}"
        )

    return caption


def format_premium_signal_details(
    sell_limit: str,
    stop_loss: str | None = None,
    target: str | None = None,
) -> str:
    """Format full real signal parameters for active premium members."""
    lines = [f"🔹 Sell limit: {sell_limit}"]
    if stop_loss:
        lines.append(f"🔹 Stop loss: {stop_loss}")
    if target:
        lines.append(f"🔹 Target: {target}")
    return "\n".join(lines)
