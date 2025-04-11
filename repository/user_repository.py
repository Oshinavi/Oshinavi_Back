from models import db, User, TweetUser, UserOshi

# 회원 정보 관련 DB 트랜잭션 정의
class UserRepository:

    # 이메일로 유저 찾기
    def find_user_by_email(self, email):
        return User.query.filter_by(email=email).first()

    # 회원가입시 유저 정보 저장
    def create_user(self, username, email, password_hash, tweet_id):
        user = User(username=username, email=email, password=password_hash, tweet_id=tweet_id)
        db.session.add(user)
        db.session.commit()
        return user

    # 트윗 유저 정보 저장
    def create_tweet_user(self, user_id, tweet_id, tweet_internal_id):
        tweet_user = TweetUser(user_id=user_id, tweet_id=tweet_id, tweet_internal_id=tweet_internal_id)
        db.session.add(tweet_user)
        db.session.commit()

    # 현재 유저의 오시 정보 불러오기
    def get_user_oshi(self, user_id: int) -> UserOshi | None:
        return UserOshi.query.filter_by(id=user_id).first()

    # 현재 유저의 오시 정보 저장
    def upsert_user_oshi(self, user_id: int, tweet_id: str, username: str):
        user_oshi = self.get_user_oshi(user_id)
        if user_oshi:
            user_oshi.oshi_tweet_id = tweet_id
            user_oshi.oshi_username = username
        else:
            new_oshi = UserOshi(id=user_id, oshi_tweet_id=tweet_id, oshi_username=username)
            db.session.add(new_oshi)
        db.session.commit()