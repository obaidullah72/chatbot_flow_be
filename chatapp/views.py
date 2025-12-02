import json
from typing import Any, Dict, List

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services import (
    continue_followups,
    finalize_followups,
    generate_question_set,
    handle_question_flow,
)


class ValidationError(Exception):
    """Raised when incoming payloads do not match the expected schema."""


def _parse_request_body(request) -> Dict[str, Any]:
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError("Request body must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Root payload must be a JSON object.")

    return payload


def _require_fields(payload: Dict[str, Any], fields: List[str]) -> None:
    missing = [field for field in fields if not payload.get(field)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")


def _normalize_main_answer(payload: Dict[str, Any]) -> str:
    answer = payload.get("main_answer") or payload.get("answer")
    if not answer:
        raise ValidationError("Field 'main_answer' (or alias 'answer') is required.")
    return str(answer)


def _normalize_followup_pairs(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    followup_pairs = payload.get("followup_pairs")
    if not isinstance(followup_pairs, list):
        raise ValidationError("Field 'followup_pairs' must be a list.")

    normalized: List[Dict[str, str]] = []
    for entry in followup_pairs:
        if not isinstance(entry, dict):
            raise ValidationError("Each follow-up entry must be an object.")
        question = entry.get("question")
        answer = entry.get("answer")
        if not question or not answer:
            raise ValidationError("Follow-up entries need both question and answer.")
        normalized.append({"question": str(question), "answer": str(answer)})
    return normalized


@csrf_exempt
@require_http_methods(["POST"])
def generate_questions_view(request):
    """
    Generate a fixed set of questions (default 10) for a given topic.

    Request JSON:
        {
          "topic": "...",
          "language": "en",         # optional
          "count": 10               # optional, max 10
        }
    """

    try:
        payload = _parse_request_body(request)
        _require_fields(payload, ["topic"])
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    language = payload.get("language", "en")
    username = payload.get("user", payload.get("username", "anonymous"))
    raw_count = payload.get("count") or 10
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        count = 10

    questions = generate_question_set(
        topic=str(payload["topic"]),
        count=count,
        language=str(language),
    )

    # Save questions to database
    try:
        from .models import Question, Session
        
        session, _ = Session.objects.get_or_create(
            username=username,
            topic=str(payload["topic"]),
            language=str(language),
        )
        
        # Save all generated questions
        for idx, question_text in enumerate(questions):
            Question.objects.get_or_create(
                session=session,
                question_index=idx,
                defaults={"question_text": question_text}
            )
    except Exception as e:
        # Continue even if database save fails
        pass

    return JsonResponse(
        {
            "topic": str(payload["topic"]),
            "language": language,
            "count": len(questions),
            "questions": questions,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def answer_view(request):
    """Handle the initial answer submission and branch on the score."""

    try:
        payload = _parse_request_body(request)
        _require_fields(payload, ["topic", "user", "question"])
        main_answer = _normalize_main_answer(payload)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    language = payload.get("language", "en")
    question_index = payload.get("question_index")

    flow_result = handle_question_flow(
        topic=str(payload["topic"]),
        user=str(payload["user"]),
        question=str(payload["question"]),
        main_answer=main_answer,
        language=str(language),
        question_index=question_index,
    )

    return JsonResponse(flow_result, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def finalize_followups_view(request):
    """Finalize the evaluation after the eight follow-up answers."""

    try:
        payload = _parse_request_body(request)
        _require_fields(payload, ["topic", "user", "question"])
        main_answer = _normalize_main_answer(payload)
        followup_pairs = _normalize_followup_pairs(payload)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    language = payload.get("language", "en")
    answer_id = payload.get("answer_id")

    final_result = finalize_followups(
        topic=str(payload["topic"]),
        user=str(payload["user"]),
        question=str(payload["question"]),
        main_answer=main_answer,
        followup_pairs=followup_pairs,
        language=str(language),
        answer_id=answer_id,
    )

    return JsonResponse(final_result, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def continue_followups_view(request):
    """
    Iterative follow-up endpoint.

    Request JSON:
        {
          "topic": "...",
          "user": "...",
          "question": "...",
          "main_answer": "...",
          "language": "en",
          "followup_pairs": [
            {"question": "...", "answer": "..."},
            ...
          ]
        }
    """

    try:
        payload = _parse_request_body(request)
        _require_fields(payload, ["topic", "user", "question"])
        main_answer = _normalize_main_answer(payload)
        followup_pairs = _normalize_followup_pairs(payload)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    language = payload.get("language", "en")
    target_followups = payload.get("target_followups")
    answer_id = payload.get("answer_id")

    result = continue_followups(
        topic=str(payload["topic"]),
        user=str(payload["user"]),
        question=str(payload["question"]),
        main_answer=main_answer,
        followup_pairs=followup_pairs,
        language=str(language),
        target_followups=target_followups,
        answer_id=answer_id,
    )

    return JsonResponse(result, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def repeat_question_view(request):
    """
    Repeat the latest question (main or follow-up) so the client can surface
    it again without advancing the flow.
    """

    try:
        payload = _parse_request_body(request)
        _require_fields(payload, ["question"])
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    question_text = str(payload["question"]).strip()
    if not question_text:
        return JsonResponse({"error": "Question cannot be blank."}, status=400)

    return JsonResponse(
        {
            "repeat_prompt": question_text,
            "message": payload.get(
                "message_override",
                "Sure, let me restate the last question so we stay on the same page.",
            ),
        },
        status=200,
    )
