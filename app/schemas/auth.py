# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict

class SignupRequest(BaseModel):
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


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email:    EmailStr = Field(..., description="이메일 주소")
    password: str      = Field(..., min_length=6, description="비밀번호")


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "message": "회원가입 및 로그인 성공",
                "token":   "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        },
    )

    message: str = Field(..., description="응답 메시지")
    token:   str = Field(..., description="JWT 토큰")


class MessageResponse(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {"message": "Operation successful"}
        },
    )

    message: str = Field(..., description="응답 메시지")