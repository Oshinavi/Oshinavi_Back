import re

# ── 기존 RT 접두사 마스킹 패턴 ──────────────────────────────────────────────
RT_PATTERN = re.compile(r"^RT @\S+:\s*")

# ── 해시태그 마스킹 패턴: 공백까지 포함한 모든 '#...' 문자열 ───────────────
HASHTAG_PATTERN = re.compile(r"#\S+")

# ── 이모지 추출 패턴 (기존과 동일) ───────────────────────────────────────
EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001F6FF"  # Misc emojis
    r"\U0001F900-\U0001F9FF"   # Supplemental emojis
    r"\u2600-\u26FF"           # Misc symbols
    r"\u2700-\u27BF]"          # Dingbats
)

def mask_rt_prefix(text: str) -> tuple[str, str | None]:
    """
    RT @username: 형태의 접두사를 __RT__ 로 마스킹하고
    원본 접두사를 함께 반환
    """
    m = RT_PATTERN.match(text)
    if m:
        prefix = m.group(0)
        return text.replace(prefix, "__RT__ ", 1), prefix
    return text, None

def restore_rt_prefix(text: str, prefix: str | None) -> str:
    """
    mask_rt_prefix로 마스킹한 __RT__ 를 원본 RT 접두사로 복원
    """
    if not prefix:
        return text
    return prefix + text.replace("__RT__ ", "")

def mask_hash_emoji(text: str) -> tuple[str, str]:
    """
    모든 #태그를 순서대로 __HASH__ 토큰으로 치환하고,
    원본 태그들을 '##' 구분자로 직렬화해 반환
    """
    tags = HASHTAG_PATTERN.findall(text)
    if not tags:
        return text, ""
    masked = text
    for _ in tags:
        masked = HASHTAG_PATTERN.sub("__HASH__", masked, count=1)
    serialized = "##".join(tags)
    return masked, serialized

def restore_hash_emoji(text: str, serialized: str) -> str:
    """
    직렬화된 해시태그 리스트를 꺼내어
    __HASH__ 토큰을 순서대로 원본 해시태그로 복원
    """
    if not serialized:
        return text
    tags = serialized.split("##")
    restored = text
    for tag in tags:
        restored = restored.replace("__HASH__", tag, 1)
    return restored

def extract_emojis(text: str) -> list[str]:
    """
    텍스트에서 이모지 유니코드만 추출하여 리스트로 반환
    """
    return EMOJI_PATTERN.findall(text)