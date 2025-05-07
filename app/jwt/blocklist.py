"""
JWT 블랙리스트 (서버 메모리 기반)

✅ 사용 예:
  - 로그아웃 시 현재 JWT의 jti를 blocklist에 추가
  - 요청 수신 시 해당 jti가 blocklist에 있으면 인증 거부

❗ 운영 환경에서는 Redis 등 외부 저장소로 대체 권장
"""

from typing import Set

# 서버 메모리에 저장되는 JWT 블랙리스트
jwt_blocklist: Set[str] = set()