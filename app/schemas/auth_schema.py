from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict

# ─── 인증 관련 요청/응답 스키마 정의 ─────────────────────────────────────

class SignupRequest(BaseModel):
    """
    회원가입 요청 모델
    - 유저명, 이메일, 비밀번호 및 트위터 연동 정보(ct0, auth_token)를 포함
    """
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "username":   "username",
                "email":      "test@example.com",
                "password":   "securepassword",
                "cfpassword": "securepassword",
                "tweet_id":   "kurusurindesu",
            }
        },
    )

    username:   str      = Field(..., min_length=1, description="사용자 이름")
    email:      EmailStr = Field(..., description="이메일 주소")
    password:   str      = Field(..., min_length=6, description="비밀번호")
    cfpassword: str      = Field(..., min_length=6, description="비밀번호 확인")
    tweet_id:   str      = Field(..., description="트위터 스크린네임")
    ct0:        str      = Field(..., description="트위터 ct0 쿠키 값")
    auth_token: str      = Field(..., description="트위터 auth_token 쿠키 값")


class LoginRequest(BaseModel):
    """
    로그인 요청 모델
    - 이메일과 비밀번호를 사용하여 인증 수행
    """
    model_config = ConfigDict(extra="ignore")
    email:    EmailStr = Field(..., description="로그인용 이메일 주소")
    password: str      = Field(..., min_length=6, description="비밀번호")


class TokenResponse(BaseModel):
    """
    인증 토큰 응답 모델
    - access_token과 refresh_token, 토큰 타입 포함
    """
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "message": "로그인 성공",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        },
    )

    message: str = Field(..., description="응답 메시지")
    access_token: str = Field(..., description="Access Token")
    refresh_token: str = Field(..., description="Refresh Token")
    token_type: str = Field(default="bearer", description="토큰 타입 (기본 bearer)")


class MessageResponse(BaseModel):
    """
    단순 메시지 응답 모델
    - API 처리 결과를 간단한 메시지로 반환할 때 사용
    """
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {"message": "Operation successful"}
        },
    )

    message: str = Field(..., description="응답 메시지")