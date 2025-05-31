"""
Repository 계층 예외 클래스들
"""

from app.utils.exceptions import ApiError


class RepositoryError(ApiError):
    """Repository 관련 기본 예외"""
    pass


class DatabaseCommitError(RepositoryError):
    """DB 커밋 관련 예외"""
    pass


class DatabaseRollbackError(RepositoryError):
    """DB 롤백 관련 예외"""
    pass


class EntityNotFoundError(RepositoryError):
    """엔티티 조회 실패 예외"""
    pass


class EntityValidationError(RepositoryError):
    """엔티티 검증 실패 예외"""
    pass


class QueryExecutionError(RepositoryError):
    """쿼리 실행 관련 예외"""
    pass


class TransactionError(RepositoryError):
    """트랜잭션 관련 예외"""
    pass


class ConnectionError(RepositoryError):
    """데이터베이스 연결 관련 예외"""
    pass