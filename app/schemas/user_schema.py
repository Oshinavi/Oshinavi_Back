# app/schemas/user.py
from pydantic import BaseModel
from typing import Optional

class TweetIdResponse(BaseModel):
    tweetId: str

class UserProfileResponse(BaseModel):
    twitter_internal_id: str
    twitter_id: str
    username: str
    bio: str
    profile_image_url: Optional[str]
    profile_banner_url: Optional[str]

    class Config:
        from_attributes = True

class OshiResponse(BaseModel):
    oshi_screen_name: str
    oshi_username: str

class OshiUpdateRequest(BaseModel):
    screen_name: str