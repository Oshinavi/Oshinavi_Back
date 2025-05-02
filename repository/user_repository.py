from models import db, User, UserOshi, TwitterUser


# ─────────────────────────────────────────────────────────────────────────────
# 회원 정보 관련 DB 트랜잭션 정의
# ─────────────────────────────────────────────────────────────────────────────
class UserRepository:

    # 이메일로 유저 찾기
    def find_user_by_email(self, email):
        return User.query.filter_by(email=email).first()

    # 트위터 고유값 id로 유저 찾기
    def get_twitter_user_by_internal_id(self, internal_id: str) -> TwitterUser | None:
        return TwitterUser.query.get(internal_id)

    # 회원가입시 유저 정보 저장
    def create_user(
            self,
            username: str,
            email: str,
            password_hash: str,
            twitter_user_internal_id: str | None = None
            ) -> User:

        user = User(
            username=username,
            email=email,
            password=password_hash,
            twitter_user_internal_id=twitter_user_internal_id
        )
        db.session.add(user)
        db.session.commit()
        return user

    # 실제 트위터 유저 정보 저장
    def create_twitter_user(
            self,
            twitter_internal_id: str,
            twitter_id: str,
            username: str
    )-> TwitterUser:
        twitter_user = TwitterUser(
            twitter_internal_id=twitter_internal_id,
            twitter_id=twitter_id,
            username=username
        )
        db.session.add(twitter_user)
        db.session.commit()
        return twitter_user

    # 현재 유저의 오시 정보 불러오기
    def get_user_oshi(self, user_id: int) -> UserOshi | None:
        return UserOshi.query.filter_by(user_id=user_id).first()

    # 현재 유저의 오시 정보 저장
    def upsert_user_oshi(self, user_id: int, oshi_internal_id: str):
        user_oshi = self.get_user_oshi(user_id)
        if user_oshi:
            user_oshi.oshi_internal_id = oshi_internal_id
        else:
            new_oshi = UserOshi(user_id=user_id, oshi_internal_id=oshi_internal_id)
            db.session.add(new_oshi)
        db.session.commit()