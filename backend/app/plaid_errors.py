import json
from typing import Any

from plaid import ApiException


def plaid_user_message(exc: Exception, max_len: int = 500) -> str:
    if isinstance(exc, ApiException) and exc.body:
        raw = exc.body
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        try:
            data: dict[str, Any] = json.loads(raw)
            msg = (
                data.get("display_message")
                or data.get("error_message")
                or data.get("error_code")
            )
            if msg:
                return str(msg)[:max_len]
        except (json.JSONDecodeError, TypeError):
            pass
    text = str(exc)
    return text[:max_len]


def plaid_error_payload(exc: Exception) -> dict:
    if isinstance(exc, ApiException):
        msg = plaid_user_message(exc)
        payload: dict[str, Any] = {
            "error": "Plaid API request failed",
            "message": msg,
            "details": msg,
        }
        if exc.body:
            raw = exc.body
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
                if isinstance(body, dict):
                    if body.get("error_code"):
                        payload["error_code"] = body["error_code"]
                    if body.get("error_type"):
                        payload["error_type"] = body["error_type"]
            except json.JSONDecodeError:
                pass
        return payload
    return {
        "error": "Unexpected server error",
        "message": str(exc)[:500],
        "details": str(exc)[:500],
    }


def plaid_http_status(exc: ApiException) -> int:
    code = exc.status
    if code is None or not (400 <= code < 600):
        return 502
    return code
