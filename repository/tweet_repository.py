from models import db, Post, ReplyLog

# 트윗(포스트) 정보 관련 DB 트랜잭션 정의
class TweetRepository:

    # 트윗 id 불러오기
    def get_existing_tweet_ids(self) -> set[str]:
        print("기존 트윗 ID 불러오기")
        return {str(row[0]) for row in db.session.query(Post.tweet_id).all()}

    # 트윗 정보 db에 저장
    def save_post(self, *, tweet_id, tweet_userid, tweet_username, tweet_date,
                  tweet_included_date, tweet_text, tweet_translated_text, tweet_about) -> Post:
        new_post = Post(
            tweet_id=tweet_id,
            tweet_userid=tweet_userid,
            tweet_username=tweet_username,
            tweet_date=tweet_date,
            tweet_included_date=tweet_included_date,
            tweet_text=tweet_text,
            tweet_translated_text=tweet_translated_text,
            tweet_about=tweet_about
        )
        db.session.add(new_post)
        return new_post

    # 여러개의 트윗 정보 db에 저장
    def save_all(self, posts: list[Post]):
        print(f"총 {len(posts)}개 포스트 DB에 저장 요청")
        db.session.commit()

    # 최근 트윗 가져오기
    def get_recent_posts(self, limit: int = 20):
        return Post.query.order_by(Post.tweet_date.desc()).limit(limit).all()

    # 해당 유저가 작성한 최근 트윗 가져오기
    def get_recent_posts_by_username(self, username: str, limit: int = 20):
        return Post.query.filter_by(tweet_username=username) \
            .order_by(Post.tweet_date.desc()) \
            .limit(limit) \
            .all()

    def save_reply_log(self, tweet_id: str, reply_text: str):
        log = ReplyLog(tweet_id=tweet_id, reply_text=reply_text)
        db.session.add(log)
        db.session.commit()
