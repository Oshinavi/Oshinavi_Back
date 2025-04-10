# import asyncio
# from routes.tweet_profile_controller import get_twitter_id_by_username as twikit_fetch
#
# def get_twitter_id_by_username(tweet_id: str):
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     return loop.run_until_complete(twikit_fetch(tweet_id))