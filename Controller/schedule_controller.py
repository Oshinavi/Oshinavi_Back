# Controller/schedule_controller.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.schedule_service import ScheduleService
from services.user_service import UserService
from services.exceptions import ApiError
from datetime import datetime

schedule_bp = Blueprint('schedules', __name__)

schedule_svc = ScheduleService()
user_svc = UserService()

def parse_iso8601(dt_str: str) -> datetime:
    """
    문자열 ISO8601 형식 → datetime 변환. 실패 시 ApiError(400) 발생.
    """
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        raise ApiError("날짜 형식이 잘못되었습니다. ISO8601 형식으로 보내주세요.", status_code=400)

def _serialize_schedule(sched):
    """SQLAlchemy Schedule 엔티티를 JSON 직렬화 가능한 dict로 변환."""
    return {
        'id': sched.id,
        'title': sched.title,
        'category': sched.category,
        'start_at': sched.start_at.isoformat(),
        'end_at': sched.end_at.isoformat(),
        'description': sched.description,
        'related_twitter_internal_id': sched.related_twitter_internal_id,
        'created_by_user_id': sched.created_by_user_id,
    }

# 스케줄 등록
@schedule_bp.route('', methods=['POST'])
@jwt_required()
def create_schedule():
    data = request.get_json() or {}
    try:
        # 1) 필수 필드 검증
        for field in (
            'title', 'category', 'start_at', 'end_at',
            'description', 'related_twitter_screen_name'
        ):
            if not data.get(field):
                raise ApiError(f"필수 항목 '{field}'이(가) 누락되었습니다.", status_code=400)

        # 2) 파싱
        title = data['title']
        category = data['category']
        start_at = parse_iso8601(data['start_at'])
        end_at   = parse_iso8601(data['end_at'])
        description = data['description']
        screen_name = data['related_twitter_screen_name']

        # 3) 현재 로그인한 사용자 조회
        user_email = get_jwt_identity()
        user = user_svc.user_repo.find_by_email(user_email)
        if not user:
            raise ApiError("사용자를 찾을 수 없습니다.", status_code=404)
        created_by_user_id = user.id

        # 4) 서비스 호출
        sched = schedule_svc.create_schedule(
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            description=description,
            related_twitter_screen_name=screen_name,
            created_by_user_id=created_by_user_id
        )

        return jsonify(_serialize_schedule(sched)), 201

    except ApiError as e:
        return e.to_response()

# 내 스케줄 목록 조회
@schedule_bp.route('', methods=['GET'])
@jwt_required()
def list_schedules():
    try:
        user_email = get_jwt_identity()
        user = user_svc.user_repo.find_by_email(user_email)
        if not user:
            raise ApiError("사용자를 찾을 수 없습니다.", status_code=404)

        schedules = schedule_svc.list_my_oshi_schedules(user.id)
        return jsonify([_serialize_schedule(s) for s in schedules]), 200

    except ApiError as e:
        return e.to_response()

# 스케줄 수정
@schedule_bp.route('/<int:schedule_id>', methods=['PUT'])
@jwt_required()
def update_schedule(schedule_id: int):
    data = request.get_json() or {}
    try:
        user_email = get_jwt_identity()
        user = user_svc.user_repo.find_by_email(user_email)
        if not user:
            raise ApiError("사용자를 찾을 수 없습니다.", status_code=404)

        # 업데이트할 필드 수집
        kwargs = {}
        if 'title' in data:    kwargs['title'] = data['title']
        if 'category' in data: kwargs['category'] = data['category']
        if 'start_at' in data: kwargs['start_at'] = parse_iso8601(data['start_at'])
        if 'end_at' in data:   kwargs['end_at']   = parse_iso8601(data['end_at'])
        if 'description' in data: kwargs['description'] = data['description']
        if 'related_twitter_screen_name' in data:
            kwargs['related_twitter_screen_name'] = data['related_twitter_screen_name']

        sched = schedule_svc.edit_schedule(schedule_id, user.id, **kwargs)
        return jsonify(_serialize_schedule(sched)), 200

    except ApiError as e:
        return e.to_response()

# 스케줄 삭제
@schedule_bp.route('/<int:schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_schedule(schedule_id: int):
    try:
        user_email = get_jwt_identity()
        user = user_svc.user_repo.find_by_email(user_email)
        if not user:
            raise ApiError("로그인된 사용자를 찾을 수 없습니다.", status_code=404)

        schedule_svc.delete_schedule(schedule_id, user.id)
        return jsonify({"message": "삭제 성공"}), 200

    except ApiError as e:
        return e.to_response()