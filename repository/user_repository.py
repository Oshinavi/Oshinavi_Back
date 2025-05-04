import logging

from models import db, User, UserOshi, TwitterUser
from services.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 회원 정보 관련 DB 트랜잭션 정의
# ─────────────────────────────────────────────────────────────────────────────
class UserRepository:

    # 이메일로 유저 찾기
    def find_by_email(self, email):
        return User.query.filter_by(email=email).first()

    # 트위터 고유값 id로 유저 찾기
    def get_twitter_user(self, internal_id: str) -> TwitterUser | None:
        twituser = TwitterUser.query.get(internal_id)
        # 반드시 있어야 하는 엔티티는 서비스가 아닌 리포지토리 단에서 다음과 같이 미리 처리해 줘, 로직을 간결하게 하고 도메인 규칙을 명확화
        if not twituser:
            logger.debug(f"TwitterUser {internal_id} not found")
            raise NotFoundError(f"TwitterUser({internal_id}) not found")
        return twituser

    # 회원가입시 유저 정보 저장
    def add_user(self, user: User) -> None:
        db.session.add(user)

    # 실제 트위터 유저 정보 저장
    def add_twitter_user(self, twitter_user: TwitterUser) -> None:
        db.session.add(twitter_user)

    # 현재 유저의 오시 정보 불러오기
    def get_user_oshi(self, user_id: int) -> UserOshi | None:
        return UserOshi.query.filter_by(user_id=user_id).first()

    # 현재 유저의 오시 정보 저장
    def upsert_user_oshi(self, user_id: int, oshi_internal_id: str) -> UserOshi:
        """
        user_id에 대응하는 UserOshi 레코드를 얻어와서,
        있으면 internal_id만 갱신, 없으면 새로 추가.
        커밋은 Service 레이어가 담당.
        """
        user_oshi = self.get_user_oshi(user_id)
        if user_oshi:
            user_oshi.oshi_internal_id = oshi_internal_id
        else:
            new_oshi = UserOshi(user_id=user_id, oshi_internal_id=oshi_internal_id)
            db.session.add(new_oshi)
        return user_oshi

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()

