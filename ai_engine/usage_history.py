from __future__ import annotations

from typing import Any

from .models import AIModelUsageHistory


def _get_subscription_snapshot(user):
    try:
        subscription = user.subscription
    except Exception:
        return None, '', '', ''

    plan = getattr(subscription, 'plan', None)
    return (
        subscription,
        getattr(plan, 'name', '') or '',
        getattr(plan, 'plan_type', '') or '',
        getattr(subscription, 'status', '') or '',
    )


def record_model_usage(
    *,
    user=None,
    service_name: str,
    operation: str = '',
    model_artifact=None,
    model_identifier: str = '',
    model_version: str = '',
    request_path: str = '',
    request_metadata: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
    confidence: float | None = None,
    success: bool = True,
    error_message: str = '',
    response_time_ms: int | None = None,
    request=None,
):
    subscription = None
    subscription_plan_name = ''
    subscription_plan_type = ''
    subscription_status = ''

    if user is not None:
        subscription, subscription_plan_name, subscription_plan_type, subscription_status = _get_subscription_snapshot(user)

    ip_address = None
    user_agent = ''
    if request is not None:
        meta = getattr(request, 'META', {})
        forwarded_for = meta.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            ip_address = forwarded_for.split(',')[0].strip() or None
        else:
            ip_address = meta.get('REMOTE_ADDR') or None
        user_agent = (meta.get('HTTP_USER_AGENT') or '')[:255]

    if model_artifact is not None:
        model_identifier = model_identifier or getattr(model_artifact, 'display_name', '') or ''
        model_version = model_version or getattr(model_artifact, 'version', '') or ''
        operation = operation or getattr(model_artifact, 'operation', '') or ''

    return AIModelUsageHistory.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        subscription=subscription,
        model_artifact=model_artifact,
        service_name=service_name,
        operation=operation,
        model_identifier=model_identifier,
        model_version=model_version,
        request_path=request_path,
        user_role=getattr(user, 'role', '') or '',
        subscription_plan_name=subscription_plan_name,
        subscription_plan_type=subscription_plan_type,
        subscription_status=subscription_status,
        request_metadata=request_metadata or {},
        response_metadata=response_metadata or {},
        confidence=confidence,
        success=success,
        error_message=error_message or '',
        response_time_ms=response_time_ms,
        ip_address=ip_address,
        user_agent=user_agent,
    )