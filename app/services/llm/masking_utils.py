import re

RT_PATTERN = re.compile(r"^RT @\S+:")
HASH_EMOJI = '#\u20E3'
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]")

def mask_rt_prefix(text: str) -> tuple[str, str | None]:
    m = RT_PATTERN.match(text)
    if m:
        prefix = m.group(0)
        return text.replace(prefix, "__RT__ ", 1), prefix
    return text, None

def restore_rt_prefix(text: str, prefix: str | None) -> str:
    if not prefix:
        return text
    return f"{prefix}{text.replace('__RT__ ', '')}"

def mask_hash_emoji(text: str) -> tuple[str, str | None]:
    if HASH_EMOJI in text:
        return text.replace(HASH_EMOJI, "__HASH__"), HASH_EMOJI
    return text, None

def restore_hash_emoji(text: str, emoji: str | None) -> str:
    return text.replace("__HASH__", emoji) if emoji else text

def extract_emojis(text: str) -> list[str]:
    return EMOJI_PATTERN.findall(text)