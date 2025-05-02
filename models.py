from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ─────────────────────────────────────────────────────────────────────────────
# 1) 가입된 서비스 사용자
# ─────────────────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'user'

    id   = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    # TwitterUser 테이블과 1:1 관계
    twitter_user_internal_id = db.Column(
        db.String(120),
        db.ForeignKey('twitter_user.twitter_internal_id'),
        nullable=True,
        unique=True
    )
    twitter_user = db.relationship(
        'TwitterUser',
        back_populates='service_user',
        uselist=False
    )

    # 이 사용자가 지정한 '오시'
    user_oshi = db.relationship(
        'UserOshi',
        back_populates='user',
        uselist=False
    )

    def __init__(self, username, email, password, twitter_user_internal_id=None):
        self.username = username
        self.email    = email
        self.password = password
        self.twitter_user_internal_id = twitter_user_internal_id


# ─────────────────────────────────────────────────────────────────────────────
# 2) 트위터 상의 유저 정보
# ─────────────────────────────────────────────────────────────────────────────
class TwitterUser(db.Model):
    __tablename__ = 'twitter_user'

    # 외부 트위터 내부 ID (PK)
    twitter_internal_id = db.Column(db.String(120), primary_key=True)
    # 스크린네임 (변경 가능하므로 unique)
    twitter_id = db.Column(db.String(120), unique=True, nullable=False)
    # 실제 트위터 이름(별명)
    username = db.Column(db.String(120), nullable=False)

    # 서비스 User 와 1:1
    service_user = db.relationship(
        'User',
        back_populates='twitter_user',
        uselist=False
    )

    # 여러 UserOshi의 대상(fan) 관계
    fans = db.relationship(
        'UserOshi',
        back_populates='oshi',
        cascade='all, delete-orphan'
    )

    posts = db.relationship(
        'Post',
        back_populates='author',
        cascade='all, delete-orphan'
    )

    def __init__(self, twitter_internal_id, twitter_id, username):
        self.twitter_internal_id = twitter_internal_id
        self.twitter_id = twitter_id
        self.username = username


# ─────────────────────────────────────────────────────────────────────────────
# 3) 사용자가 지정한 ‘오시’ 정보
# ─────────────────────────────────────────────────────────────────────────────
class UserOshi(db.Model):
    __tablename__ = 'user_oshi'

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        unique=True,
        primary_key=True
    )
    oshi_internal_id = db.Column(
        db.String(120),
        db.ForeignKey('twitter_user.twitter_internal_id'),
        unique=True,
        nullable=False
    )

    # 관계 설정
    user = db.relationship(
        'User',
        back_populates='user_oshi'
    )
    oshi = db.relationship(
        'TwitterUser',
        back_populates='fans'
    )  # 이 트위터 유저를 오시로 등록한 유저들


# ─────────────────────────────────────────────────────────────────────────────
# 4) 트윗 포스트 정보
# ─────────────────────────────────────────────────────────────────────────────
class Post(db.Model):
    __tablename__ = 'post'

    tweet_id = db.Column(db.BigInteger, primary_key=True)
    # 작성자 참조 (TwitterUser)
    author_internal_id = db.Column(
        db.String(120),
        db.ForeignKey('twitter_user.twitter_internal_id'),
        nullable=False
    )
    tweet_date = db.Column(db.DateTime, nullable=False)
    tweet_included_date = db.Column(db.DateTime, nullable=True)
    tweet_text = db.Column(db.Text, nullable=False)
    tweet_translated_text = db.Column(db.Text, nullable=False)
    tweet_about = db.Column(db.String(255), nullable=False)

    author = db.relationship(
        'TwitterUser',
        back_populates='posts',
        foreign_keys=[author_internal_id]
    )

    def __init__(self, tweet_id, author_internal_id, tweet_date,
                 tweet_included_date, tweet_text, tweet_translated_text, tweet_about):
        self.tweet_id = tweet_id
        self.author_internal_id = author_internal_id
        self.tweet_date = tweet_date
        self.tweet_included_date = tweet_included_date
        self.tweet_text = tweet_text
        self.tweet_translated_text = tweet_translated_text
        self.tweet_about = tweet_about


# ─────────────────────────────────────────────────────────────────────────────
# 5) 좋아요 정보
# ─────────────────────────────────────────────────────────────────────────────
class TweetLikes(db.Model):
    __tablename__ = 'tweet_likes'

    # 포스트 ID
    post_tweet_id   = db.Column(
        db.BigInteger,
        db.ForeignKey('post.tweet_id'),
        primary_key=True
    )
    # 좋아요를 누른 유저 id
    liked_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        primary_key=True
    )
    # 좋아요 등록 시점
    liked_at        = db.Column(db.DateTime, nullable=False)

    # 관계 설정
    post = db.relationship('Post', backref='likes')
    user = db.relationship('User', backref='liked_posts')

    def __init__(self, tweet_id, tweet_userid, liked_at):
        self.tweet_id = tweet_id
        self.tweet_userid = tweet_userid
        self.liked_at = liked_at


# ─────────────────────────────────────────────────────────────────────────────
# 6) 리플라이(댓글) 로그
# ─────────────────────────────────────────────────────────────────────────────
class ReplyLog(db.Model):
    __tablename__ = 'reply_log'

    id        = db.Column(db.Integer, primary_key=True)
    post_tweet_id = db.Column(
        db.BigInteger,
        db.ForeignKey('post.tweet_id'),
        nullable=False
    )
    reply_text  = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, server_default=db.func.now())

    # 관계 설정
    post = db.relationship('Post', backref='replies')

    def __init__(self, post_tweet_id, reply_text):
        self.post_tweet_id = post_tweet_id
        self.reply_text    = reply_text