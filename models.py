from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)  # 고유한 사용자 ID
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    tweet_id = db.Column(db.String(120), unique=True, nullable=True)  # 트위터 ID (선택 사항)

    # TweetUser와의 관계
    tweet_user = db.relationship('TweetUser', back_populates='user', uselist=False)

    # UserOshi와의 관계
    user_oshi = db.relationship('UserOshi', back_populates='user', uselist=False)

    def __init__(self, username, email, password, tweet_id=None):
        self.username = username
        self.email = email
        self.password = password
        self.tweet_id = tweet_id


class TweetUser(db.Model):
    __tablename__ = 'tweet_user'
    tweet_internal_id = db.Column(db.String(120), primary_key=True)  # 트위터 내부 ID (PK)
    tweet_id = db.Column(db.String(120), unique=True, nullable=False)  # 변경 가능성이 있는 외부 ID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # `User` 테이블과 연결

    # User와의 관계
    user = db.relationship('User', back_populates='tweet_user')

    def __init__(self, tweet_internal_id, tweet_id, user_id):
        self.tweet_internal_id = tweet_internal_id
        self.tweet_id = tweet_id
        self.user_id = user_id

    @staticmethod
    def get_user_profile(tweet_id):
        user_profile = TweetUser.query.filter_by(tweetId=tweet_id).first()
        return user_profile.to_dict() if user_profile else None

    def to_dict(self):
        return {
            'tweet_id': self.tweet_id,
            'bio': self.bio
        }


class UserOshi(db.Model):
    __tablename__ = 'user_oshi'
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)  # User 테이블과 연결
    oshi_tweet_id = db.Column(db.String(120), nullable=False, unique=True)  # 오시의 트위터 ID
    oshi_username = db.Column(db.String(120), nullable=True)  # 오시 유저네임

    # User와의 관계
    user = db.relationship('User', back_populates='user_oshi')

    def __init__(self, id, oshi_tweet_id, oshi_username=None):
        self.id = id
        self.oshi_tweet_id = oshi_tweet_id
        self.oshi_username = oshi_username


class Post(db.Model):
    __tablename__ = 'post'
    tweet_id = db.Column(db.BigInteger, primary_key=True)
    tweet_userid = db.Column(db.String(255), nullable=False)
    tweet_username = db.Column(db.String(255), nullable=False)
    tweet_date = db.Column(db.DateTime, nullable=False)
    tweet_included_date = db.Column(db.DateTime, nullable=True)
    tweet_text = db.Column(db.Text, nullable=False)
    tweet_translated_text = db.Column(db.Text, nullable=False)
    tweet_about = db.Column(db.String(255), nullable=False)

    def __init__(self, tweet_id, tweet_userid, tweet_username, tweet_date,
                 tweet_included_date, tweet_text, tweet_translated_text, tweet_about):
        self.tweet_id = tweet_id
        self.tweet_userid = tweet_userid
        self.tweet_username = tweet_username
        self.tweet_date = tweet_date
        self.tweet_included_date = tweet_included_date
        self.tweet_text = tweet_text
        self.tweet_translated_text = tweet_translated_text
        self.tweet_about = tweet_about