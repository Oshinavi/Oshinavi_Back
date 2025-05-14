"""
JWT 블랙리스트 모듈

서버 메모리 기반으로 JWT ID(jti)를 관리
- 로그아웃 시 jti를 블랙리스트에 추가하여 토큰을 무효화.
- 인증 처리 시 블랙리스트에 등재된 jti는 인증 거부 대상

나중에 운영 환경에서는 단일 서버 메모리 대신 Redis 등 외부저장소로 바꿔야함
"""

from typing import Set

# 서버 메모리에 저장되는 JWT 블랙리스트
jwt_blocklist: Set[str] = set()