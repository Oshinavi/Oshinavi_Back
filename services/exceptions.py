from flask import jsonify

class ApiError(Exception):
    """
    기본 API 예외 클래스.
    메시지와 상태 코드를 커스터마이징 가능.
    """
    status_code = 500

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        # status_code가 전달되면 기본값을 덮어씀.
        if status_code is not None:
            self.status_code = status_code

    def to_response(self):
        return jsonify({"error": self.message}), self.status_code

class BadRequestError(ApiError):
    status_code = 400

class UnauthorizedError(ApiError):
    status_code = 401

class NotFoundError(ApiError):
    status_code = 404

class ConflictError(ApiError):
    status_code = 409