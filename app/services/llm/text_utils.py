import re
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TextMasker:
    """
    텍스트 전처리 및 후처리를 위한 유틸리티 클래스

    - RT 접두사 마스킹/복원
    - 해시태그 마스킹/복원 (번역 방지 강화)
    - 이모지(ex. 😂, 🌱 등) 추출
    """

    # RT 토큰
    RT_TOKEN = "【RTMASK】"

    # 해시태그 플레이스홀더
    HASH_PLACEHOLDER_PREFIX = "【HASHTAG_"
    HASH_PLACEHOLDER_SUFFIX = "】"

    # "RT @username:" 패턴 (문장 맨 앞에만 적용)
    RT_PATTERN = re.compile(r"^RT @[\w]+:\s*")

    # 해시태그 패턴
    HASHTAG_PATTERN = re.compile(
        r"#([A-Za-z0-9_가-힣\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+)"
    )

    # 이모지 추출 범위
    EMOJI_PATTERN = re.compile(
        r"[\U0001F300-\U0001F6FF"  # 기타 픽토그램
        r"\U0001F900-\U0001F9FF"  # 추가 보충 이모지
        r"\u2600-\u26FF"  # 기타 기호
        r"\u2700-\u27BF]"  # 딩뱃 기호
    )

    @classmethod
    def mask_rt_prefix(cls, text: str) -> Tuple[str, Optional[str]]:
        """
        'RT @username:' 형식을 번역되지 않는 안전한 토큰으로 치환
        - 반환값: (마스킹된 텍스트, 원본 prefix)
        """
        match = cls.RT_PATTERN.match(text)
        if not match:
            return text, None

        prefix = match.group(0)  # ex) "RT @cocona_nonaka: "
        masked = text.replace(prefix, f"{cls.RT_TOKEN} ", 1)
        logger.debug(f"RT 마스킹: {prefix} -> {cls.RT_TOKEN}")
        return masked, prefix

    @classmethod
    def restore_rt_prefix(cls, text: str, original_prefix: Optional[str]) -> str:
        """
        안전한 토큰을 원본 RT 접두사("RT @username: ")로 복원
        """
        if not original_prefix:
            return text

        restored = text.replace(f"{cls.RT_TOKEN} ", original_prefix, 1)
        logger.debug(f"RT 복원: {cls.RT_TOKEN} -> {original_prefix}")
        return restored

    @classmethod
    def mask_hashtags(cls, text: str) -> Tuple[str, List[Tuple[str, str]]]:
        """
        원문에서 해시태그를 찾아 번역되지 않는 안전한 플레이스홀더로 바꾸고 원본 해시태그와 플레이스홀더 매핑을 반환

        플레이스홀더 형태: 【HASHTAG_001】
        - 반환값: (마스킹된 텍스트, [(플레이스홀더, "#원본태그"), ...])
        """
        # 1) 원문에서 해시태그 전체 조회
        hashtags = cls.HASHTAG_PATTERN.findall(text)
        if not hashtags:
            return text, []

        masked = text
        tag_mappings: List[Tuple[str, str]] = []

        for idx, body in enumerate(hashtags):
            full_tag = f"#{body}"

            # 간단한 인덱스 기반 플레이스홀더
            placeholder = f"{cls.HASH_PLACEHOLDER_PREFIX}{idx + 1:03d}{cls.HASH_PLACEHOLDER_SUFFIX}"

            # 발견되는 첫 번째 full_tag만 플레이스홀더로 치환
            if full_tag in masked:
                masked = masked.replace(full_tag, placeholder, 1)
                tag_mappings.append((placeholder, full_tag))
                logger.debug(f"해시태그 마스킹: {full_tag} -> {placeholder}")

        return masked, tag_mappings

    @classmethod
    def restore_hashtags(cls, text: str, tag_mappings: List[Tuple[str, str]]) -> str:
        """
        플레이스홀더를 원본 해시태그로 복원
        """
        restored = text

        for placeholder, original_tag in tag_mappings:
            if placeholder in restored:
                restored = restored.replace(placeholder, original_tag, 1)
                logger.debug(f"해시태그 복원 성공: {placeholder} -> {original_tag}")
            else:
                logger.warning(f"플레이스홀더를 찾을 수 없음: {placeholder}")

                # 가능한 변형된 형태들을 확인
                # LLM이 【】를 다른 기호로 바꿨을 가능성
                potential_forms = [
                    placeholder.replace("【", "[").replace("】", "]"),  # [HASHTAG_001]
                    placeholder.replace("【", "(").replace("】", ")"),  # (HASHTAG_001)
                    placeholder.replace("【", "<").replace("】", ">"),  # <HASHTAG_001>
                    placeholder.replace("【HASHTAG_", "HASHTAG_").replace("】", ""),  # HASHTAG_001
                    f"#{placeholder}",  # #【HASHTAG_001】
                ]

                found = False
                for form in potential_forms:
                    if form in restored:
                        restored = restored.replace(form, original_tag, 1)
                        logger.info(f"변형된 플레이스홀더 복원: {form} -> {original_tag}")
                        found = True
                        break

                if not found:
                    # 부분 매칭 시도 (숫자 부분만 남아있을 경우)
                    prefix = cls.HASH_PLACEHOLDER_PREFIX
                    suffix = cls.HASH_PLACEHOLDER_SUFFIX
                    number_part = placeholder.replace(prefix, "").replace(suffix, "")

                    if number_part.isdigit():
                        possible_remnants = [f"#{number_part}", number_part, f"HASHTAG_{number_part}"]
                        for remnant in possible_remnants:
                            if remnant in restored:
                                restored = restored.replace(remnant, original_tag, 1)
                                logger.info(f"부분 매칭으로 복원: {remnant} -> {original_tag}")
                                found = True
                                break

                if not found:
                    logger.error(f"해시태그 복원 완전 실패: {placeholder} -> {original_tag}")
                    # 최후의 수단: 원본 태그를 텍스트 끝에 추가
                    restored += f" {original_tag}"
                    logger.info(f"해시태그를 텍스트 끝에 추가: {original_tag}")

        return restored

    @classmethod
    def extract_emojis(cls, text: str) -> List[str]:
        """
        텍스트 내 모든 이모지(Unicode 영역)를 리스트로 추출
        """
        return cls.EMOJI_PATTERN.findall(text)

class TextMaskerStatic:
    """
    정적 메서드 버전 - 타입 힌트 오류 완전 해결
    """

    # 클래스 상수들
    RT_TOKEN = "【RTMASK】"
    HASH_PLACEHOLDER_PREFIX = "【HASHTAG_"
    HASH_PLACEHOLDER_SUFFIX = "】"
    RT_PATTERN = re.compile(r"^RT @[\w]+:\s*")
    HASHTAG_PATTERN = re.compile(r"#([A-Za-z0-9_가-힣\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+)")
    EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]")

    @staticmethod
    def mask_rt_prefix(text: str) -> Tuple[str, Optional[str]]:
        """RT 접두사 마스킹 (정적 메서드)"""
        match = TextMaskerStatic.RT_PATTERN.match(text)
        if not match:
            return text, None

        prefix = match.group(0)
        masked = text.replace(prefix, f"{TextMaskerStatic.RT_TOKEN} ", 1)
        logger.debug(f"RT 마스킹: {prefix} -> {TextMaskerStatic.RT_TOKEN}")
        return masked, prefix

    @staticmethod
    def restore_rt_prefix(text: str, original_prefix: Optional[str]) -> str:
        """RT 접두사 복원 (정적 메서드)"""
        if not original_prefix:
            return text

        restored = text.replace(f"{TextMaskerStatic.RT_TOKEN} ", original_prefix, 1)
        logger.debug(f"RT 복원: {TextMaskerStatic.RT_TOKEN} -> {original_prefix}")
        return restored

    @staticmethod
    def mask_hashtags(text: str) -> Tuple[str, List[Tuple[str, str]]]:
        """해시태그 마스킹 (정적 메서드)"""
        hashtags = TextMaskerStatic.HASHTAG_PATTERN.findall(text)
        if not hashtags:
            return text, []

        masked = text
        tag_mappings: List[Tuple[str, str]] = []

        for idx, body in enumerate(hashtags):
            full_tag = f"#{body}"
            placeholder = f"{TextMaskerStatic.HASH_PLACEHOLDER_PREFIX}{idx + 1:03d}{TextMaskerStatic.HASH_PLACEHOLDER_SUFFIX}"

            if full_tag in masked:
                masked = masked.replace(full_tag, placeholder, 1)
                tag_mappings.append((placeholder, full_tag))
                logger.debug(f"해시태그 마스킹: {full_tag} -> {placeholder}")

        return masked, tag_mappings

    @staticmethod
    def restore_hashtags(text: str, tag_mappings: List[Tuple[str, str]]) -> str:
        """해시태그 복원 (정적 메서드)"""
        restored = text

        for placeholder, original_tag in tag_mappings:
            if placeholder in restored:
                restored = restored.replace(placeholder, original_tag, 1)
                logger.debug(f"해시태그 복원 성공: {placeholder} -> {original_tag}")
            else:
                logger.warning(f"플레이스홀더를 찾을 수 없음: {placeholder}")

        return restored

    @staticmethod
    def extract_emojis(text: str) -> List[str]:
        """이모지 추출 (정적 메서드)"""
        return TextMaskerStatic.EMOJI_PATTERN.findall(text)