import re
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class TextMasker:
    """
    텍스트 전처리 및 후처리를 위한 유틸리티 클래스

    - RT 접두사 마스킹/복원
    - 해시태그 마스킹/복원
    - 이모지 추출
    """
    RT_TOKEN = "__RT__"
    HASH_TOKEN = "__HASH__"

    # 기존 RT 접두사 마스킹 패턴
    RT_PATTERN = re.compile(r"^RT @\S+:\s*")
    # 해시태그 마스킹 패턴
    HASHTAG_PATTERN = re.compile(r"#\S+")
    # 이모지 추출 패턴
    EMOJI_PATTERN = re.compile(
        r"[\U0001F300-\U0001F6FF" # Misc emojis
        r"\U0001F900-\U0001F9FF" # Supplemental emojis
        r"\u2600-\u26FF" # Misc symbols
        r"\u2700-\u27BF]" # Dingbats
    )

    @classmethod
    def mask_rt_prefix(cls, text: str) -> Tuple[str, Optional[str]]:
        """
        'RT @username:' 접두사를 RT_TOKEN으로 대체하고, 원본 접두사를 반환
        Returns:
            masked_text: 접두사가 마스킹된 텍스트
            original_prefix: 마스킹 전 원본 접두사 (없으면 None)
        """
        match = cls.RT_PATTERN.match(text)
        if not match:
            return text, None
        prefix = match.group(0)
        masked = text.replace(prefix, f"{cls.RT_TOKEN} ", 1)
        return masked, prefix

    @classmethod
    def restore_rt_prefix(cls, text: str, original_prefix: Optional[str]) -> str:
        """
        RT_TOKEN을 원본 접두사로 복원
        """
        if not original_prefix:
            return text
        return text.replace(f"{cls.RT_TOKEN} ", original_prefix, 1)

    @classmethod
    def mask_hashtags(cls, text: str) -> Tuple[str, List[str]]:
        """
        모든 해시태그를 HASH_TOKEN으로 대체하고 원본 태그 리스트를 반환
        Returns:
            masked_text: 해시태그가 마스킹된 텍스트
            tags: 순서대로 추출된 해시태그 리스트
        """
        tags = cls.HASHTAG_PATTERN.findall(text)
        if not tags:
            return text, []
        masked = text
        for _ in tags:
            masked = cls.HASHTAG_PATTERN.sub(cls.HASH_TOKEN, masked, count=1)
        return masked, tags

    @classmethod
    def restore_hashtags(cls, text: str, tags: List[str]) -> str:
        """
        HASH_TOKEN을 순서대로 원본 해시태그로 복원
        """
        restored = text
        for tag in tags:
            restored = restored.replace(cls.HASH_TOKEN, tag, 1)
        return restored

    @classmethod
    def extract_emojis(cls, text: str) -> List[str]:
        """
        텍스트 내 모든 이모지 유니코드를 리스트로 반환
        """
        return cls.EMOJI_PATTERN.findall(text)