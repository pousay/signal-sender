"""Signal parsing, entity preservation, and caption formatting."""

import random
import re
import time
from dataclasses import dataclass, field

MAX_CAPTION_LENGTH = 1024

ORDER_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*(buy\s*limit|sell\s*limit|buy\s*stop|sell\s*stop|buy|sell)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?)",
    re.MULTILINE,
)
STOP_LOSS_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|⚫️|\*|-)?\s*(?:stop\s*loss|stoploss|sl)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?|\[?مشاهده\]?(?:\s*\([^)]+\))?)",
    re.MULTILINE,
)
TARGET_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*((?:target|tp)(?:\s*[0-9]+)?)\s*[:=\-]?\s*([0-9]+(?:[.,][0-9]+)?|\[?مشاهده\]?(?:\s*\([^)]+\))?)",
    re.MULTILINE,
)
STOP_LOSS_REPLACE_REGEX = re.compile(
    r"(?i)((?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|⚫️|\*|-)?\s*(?:stop\s*loss|stoploss|sl)\s*[:=\-]?\s*)([0-9]+(?:[.,][0-9]+)?|\[?مشاهده\]?(?:\s*\([^)]+\))?)",
    re.MULTILINE,
)
TARGET_REPLACE_REGEX = re.compile(
    r"(?i)((?:^|[\n\r\s])(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*(?:target|tp)(?:\s*[0-9]+)?\s*[:=\-]?\s*)([0-9]+(?:[.,][0-9]+)?|\[?مشاهده\]?(?:\s*\([^)]+\))?)",
    re.MULTILINE,
)
PRICE_NOW_REPLACE_REGEX = re.compile(
    r"(?i)\[Price Now\]\(tg://time\?[^)]+\)|Price Now"
)
RISK_REWARD_REGEX = re.compile(
    r"(?i)^[ \t]*(?:⚖️\s*)?(?:risk\s*[/:\s]*r[ie]ward|rr|risk\s*to\s*reward)\s*[:=\-]?\s*.+$",
    re.MULTILINE,
)
CODE_LINE_REGEX = re.compile(r"(?i)^[ \t]*کد\s*[:=\-]?\s*.*$", re.MULTILINE)
FOOTER_INSERT_REGEX = re.compile(r"(?i)^[ \t]*(?:🆔|👤|@)", re.MULTILINE)
VALUE_REGEX = re.compile(
    r"(?i)(?:^|[\n\r\s])(?:🗻|🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*value\s*[:=\-]?\s*([^\n\r]+)",
    re.MULTILINE,
)
VALUE_STRIP_REGEX = re.compile(
    r"(?i)^[ \t]*(?:🗻|🔹|🔻|🔺|🟢|🔴|🔸|▫️|\*|-)?\s*value\s*[:=\-]?\s*.*$(?:\n|\r\n)?",
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
    targets: list[tuple[str, str | None]] = field(default_factory=list)
    value: str | None = None
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

    # 3. Targets (optional; supports Target, Target 1, Target 2, TP, etc.)
    target_matches = list(TARGET_REGEX.finditer(norm_text))
    parsed_targets: list[tuple[str, str | None]] = []
    primary_tp: str | None = None

    for m in target_matches:
        lbl = re.sub(r"\s+", " ", m.group(1).strip())
        raw_val = m.group(2).replace(",", ".")
        val = raw_val if re.match(r"^[0-9]+(?:[.,][0-9]+)?$", raw_val) else None
        parsed_targets.append((lbl, val))
        if primary_tp is None and val is not None:
            primary_tp = val

    if not primary_tp and parsed_targets:
        primary_tp = parsed_targets[0][1]

    # 4. Value (optional, e.g. '0.17لات')
    val_match = VALUE_REGEX.search(norm_text)
    val_str = val_match.group(1).strip() if val_match else None

    return ParsedSignal(
        order_type=order_type,
        entry_price=entry_price,
        stop_loss=sl_val,
        target=primary_tp,
        targets=parsed_targets,
        value=val_str,
        stop_loss_match_span=sl_span,
    )


def normalize_signal_emojis(text: str, order_type: str) -> str:
    """Normalize emojis according to signal specifications:
    - 🔵 for Buy title & order
    - 🔴 for Sell title & order
    - ⚫️ for Stop loss
    - 🟢 for Target
    """
    is_buy = "buy" in order_type.lower()
    title_emoji = "🔵" if is_buy else "🔴"
    order_emoji = "🔵" if is_buy else "🔴"

    lines = text.split("\n")
    new_lines = []
    title_updated = False

    for line in lines:
        stripped = line.strip()
        # 1. Title line containing 'سیگنال' or starting with 'خرید' / 'فروش'
        if not title_updated and (
            "سیگنال" in stripped
            or stripped.startswith("خرید")
            or stripped.startswith("فروش")
            or any(
                stripped.startswith(e) and ("خرید" in stripped or "فروش" in stripped)
                for e in ("🔹", "🔻", "🔺", "🟢", "🔴", "🔸", "▫️", "🔵", "⚫️")
            )
        ):
            clean_title = re.sub(r"^(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|🔵|⚫️|\*|-|\s)+", "", line)
            new_lines.append(f"{title_emoji} {clean_title}")
            title_updated = True
            continue

        # 2. Order line
        if ORDER_REGEX.search(line):
            clean_order = re.sub(r"^(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|🔵|⚫️|\*|-|\s)+", "", line)
            new_lines.append(f"{order_emoji} {clean_order}")
            continue

        # 3. Stop loss line
        if STOP_LOSS_REGEX.search(line):
            clean_sl = re.sub(r"^(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|🔵|⚫️|\*|-|\s)+", "", line)
            new_lines.append(f"⚫️ {clean_sl}")
            continue

        # 4. Target line
        if TARGET_REGEX.search(line):
            clean_tp = re.sub(r"^(?:🔹|🔻|🔺|🟢|🔴|🔸|▫️|🔵|⚫️|\*|-|\s)+", "", line)
            new_lines.append(f"🟢 {clean_tp}")
            continue

        new_lines.append(line)

    return "\n".join(new_lines)


def generate_public_caption(
    original_text: str,
    parsed: ParsedSignal,
    bot_username: str,
    signal_id: int,
    timestamp: int | None = None,
    risk_reward: str | None = None,
    daily_code: str | None = None,
) -> str:
    """Generate public channel caption by replacing Stop loss & Target values with deep link.

    Replaces Stop loss and Target values with `[مشاهده](https://t.me/{bot_username}?start={signal_id})`
    while preserving the entry order, surrounding text, emojis, and hashtags.
    Also wraps 'Price Now' with an interactive Telegram date timestamp link,
    standardizes the Risk/Reward line, and sets/injects the daily tracking code.

    Raises:
        CaptionTooLongError: if final caption exceeds 1024 characters.
    """
    clean_bot = bot_username.lstrip("@")
    deep_link = f"https://t.me/{clean_bot}?start={signal_id}"
    view_link = f"[مشاهده]({deep_link})"

    norm_text = original_text.replace("\r\n", "\n").replace("\r", "\n")
    norm_text = normalize_signal_emojis(norm_text, parsed.order_type)

    def _replace_sl(match: re.Match) -> str:
        prefix = match.group(1)
        return f"{prefix}{view_link}"

    caption, count = STOP_LOSS_REPLACE_REGEX.subn(_replace_sl, norm_text, count=1)
    if count == 0 and parsed.stop_loss is not None:
        raise SignalParseError("Failed to locate Stop loss value in signal text for replacement")

    def _replace_target(match: re.Match) -> str:
        prefix = match.group(1)
        return f"{prefix}{view_link}"

    caption = TARGET_REPLACE_REGEX.sub(_replace_target, caption)

    # Strip private value field from public channel post and preview demo
    caption = VALUE_STRIP_REGEX.sub("", caption)

    unix_ts = timestamp if timestamp is not None else int(time.time())
    caption = PRICE_NOW_REPLACE_REGEX.sub(f"[Price Now](tg://time?unix={unix_ts})", caption)

    # Standardize Risk/Reward line if present
    if RISK_REWARD_REGEX.search(caption):
        rr_str = risk_reward if risk_reward is not None else f"{random.uniform(1.20, 1.85):.2f}"
        caption = RISK_REWARD_REGEX.sub(f"⚖️ Risk/Reward : {rr_str}", caption, count=1)

    # Set or inject daily tracking code if provided
    if daily_code:
        code_line = f"کد : {daily_code}"
        if CODE_LINE_REGEX.search(caption):
            caption = CODE_LINE_REGEX.sub(code_line, caption, count=1)
        elif FOOTER_INSERT_REGEX.search(caption):
            match = FOOTER_INSERT_REGEX.search(caption)
            assert match is not None
            idx = match.start()
            caption = f"{caption[:idx]}{code_line}\n{caption[idx:]}"
        else:
            caption = f"{caption.rstrip()}\n{code_line}\n"

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
    targets: list[tuple[str, str | None]] | None = None,
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
        is_buy = "buy" in clean_label.lower()
        order_emoji = "🔵" if is_buy else "🔴"
        lines.append(f"{order_emoji} {clean_label}: {entry_price}")
    if stop_loss:
        lines.append(f"⚫️ Stop loss: {stop_loss}")

    if targets:
        valid_targets = [(lbl, val) for lbl, val in targets if val]
        if valid_targets:
            for lbl, val in valid_targets:
                lines.append(f"🟢 {lbl}: {val}")
        elif target:
            lines.append(f"🟢 Target: {target}")
    elif target:
        lines.append(f"🟢 Target: {target}")

    return "\n".join(lines)
