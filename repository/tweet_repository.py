from models import db, Post

class TweetRepository:
    def get_existing_tweet_ids(self) -> set[str]:
        print("🧠 기존 트윗 ID 불러오기")
        return {str(row[0]) for row in db.session.query(Post.tweet_id).all()}

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

    def save_all(self, posts: list[Post]):
        print(f"📥 총 {len(posts)}개 포스트 DB에 저장 요청")
        db.session.commit()

    def get_recent_posts(self, limit: int = 20):
        return Post.query.order_by(Post.tweet_date.desc()).limit(limit).all()
