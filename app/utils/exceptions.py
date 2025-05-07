class ApiError(Exception):
    """
    기본 API 예외 클래스.
    FastAPI의 커스텀 예외 핸들링 대상이 됨.
    """
    def __init__(self, message: str):
        self.message = message
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