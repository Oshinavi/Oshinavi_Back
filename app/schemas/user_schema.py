from pydantic import BaseModel, Field
from typing import Optional
from pydantic import ConfigDict

# ─── 사용자 관련 요청/응답 스키마 정의 ───────────────────────────────────

class TweetIdResponse(BaseModel):
    """
    로그인된 유저의 Twitter screen_name(tweet_id)를 반환하는 모델
    """
    tweetId: str = Field(
        ..., description="유저의 Twitter screen_name"
    )


class UserProfileResponse(BaseModel):
    """
    외부 트위터 사용자 프로필 정보를 반환하는 모델
    """
    twitter_internal_id: str = Field(
        ..., description="서비스 내 고유 트위터 내부 ID"
    )
    twitter_id: str = Field(
        ..., description="트위터 screen_name"
    )
    username: str = Field(
        ..., description="트위터 유저명(닉네임)"
    )
    bio: str = Field(
        ..., description="유저 자기소개"
    )
    profile_image_url: Optional[str] = Field(
        None, description="프로필 이미지 URL"
    )
    profile_banner_url: Optional[str] = Field(
        None, description="프로필 배너 이미지 URL"
    )
    model_config = ConfigDict(
        from_attributes=True
    )
    followers_count: int =  Field(
        ..., description="유저 팔로워 수"
    )
    following_count: int = Field(
        ..., description="유저 팔로잉 수"
    )

class OshiResponse(BaseModel):
    """
    유저의 오시 정보를 반환하는 모델
    """
    oshi_screen_name: str = Field(
        ..., description="관심 등록된 Twitter screen_name"
    )
    oshi_username: str = Field(
        ..., description="관심 등록된 Twitter 유저명(닉네임)"
    )

class OshiUpdateRequest(BaseModel):
    """
    유저 오시 변경 요청 모델
    """
    screen_name: str = Field(
        ..., description="새롭게 오시로 등록할 Twitter screen_name"
    )
