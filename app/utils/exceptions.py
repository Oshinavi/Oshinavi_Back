class ApiError(Exception):
    """
    기본 API 예외의 최상위 클래스
    - 모든 커스텀 API 예외가 이 클래스를 상속
    - FastAPI의 예외 핸들러에 의해 처리
    """
    def __init__(self, message: str):
        """
        - message: 사용자에게 전달할 예외 메시지 문자열
        """
        # 예외 메시지 설정
        self.message = message
        # 상위 Exception 초기화
        super().__init__(message)


class BadRequestError(ApiError):
    """400 Bad Request"""
    pass


class UnauthorizedError(ApiError):
    """401 Unauthorized"""
    pass


class NotFoundError(ApiError):
    """404 Not Found"""
    pass


class ConflictError(ApiError):
    """409 Conflict"""
    pass