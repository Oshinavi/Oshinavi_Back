from models import db, User, TweetUser

def find_user_by_email(email):
    return User.query.filter_by(email=email).first()

def create_user(username, email, password_hash, tweet_id):
    user = User(username=username, email=email, password=password_hash, tweet_id=tweet_id)
    db.session.add(user)
    db.session.commit()
    return user

def create_tweet_user(user_id, tweet_id, tweet_internal_id):
    tweet_user = TweetUser(user_id=user_id, tweet_id=tweet_id, tweet_internal_id=tweet_internal_id)
    db.session.add(tweet_user)
    db.session.commit()