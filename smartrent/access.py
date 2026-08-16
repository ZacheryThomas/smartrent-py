import re
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple

from .utils import SmartRentValidationError

ACTIVATION_TYPES = ("permanent", "temporary", "recurring")
WEEKDAYS = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)
_WEEKDAYS_BY_LOWER = {day.lower(): day for day in WEEKDAYS}
_RECURRING_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$")
_ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$"
)


def validate_positive_id(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SmartRentValidationError("{} must be a positive integer".format(name))
    return value


def _required_string(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SmartRentValidationError("{} is required".format(name))
    return value


def _optional_nonempty_string(value: Optional[str], name: str) -> Optional[str]:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise SmartRentValidationError("{} must be a non-empty string".format(name))
    return value


def validate_activation_type(activation_type: str) -> str:
    if activation_type not in ACTIVATION_TYPES:
        raise SmartRentValidationError(
            "activation_type must be permanent, temporary, or recurring"
        )
    return activation_type


def canonicalize_weekdays(days: Sequence[str]) -> Sequence[str]:
    if isinstance(days, (str, bytes)) or not days:
        raise SmartRentValidationError("recurring_repeat_on must contain weekdays")

    canonical = []
    seen = set()
    for day in days:
        if not isinstance(day, str) or day.lower() not in _WEEKDAYS_BY_LOWER:
            raise SmartRentValidationError(
                "recurring_repeat_on must use full English weekday names"
            )
        normalized = _WEEKDAYS_BY_LOWER[day.lower()]
        if normalized not in seen:
            canonical.append(normalized)
            seen.add(normalized)
    return canonical


def _parse_iso_timestamp(value: str, name: str) -> datetime:
    if not isinstance(value, str) or not _ISO_TIMESTAMP_RE.match(value):
        raise SmartRentValidationError("{} must be an ISO timestamp".format(name))

    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+0000"
    else:
        normalized = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", normalized)

    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
    )
    for timestamp_format in formats:
        try:
            return datetime.strptime(normalized, timestamp_format)
        except ValueError:
            continue
    raise SmartRentValidationError("{} must be an ISO timestamp".format(name))


def _validate_temporary_schedule(start_at: str, end_at: str) -> Tuple[str, str]:
    start = _parse_iso_timestamp(start_at, "temporary_start_at")
    end = _parse_iso_timestamp(end_at, "temporary_end_at")
    try:
        ordered = start < end
    except TypeError:
        raise SmartRentValidationError(
            "temporary timestamps must use compatible time zones"
        )
    if not ordered:
        raise SmartRentValidationError(
            "temporary_start_at must be before temporary_end_at"
        )
    return start_at, end_at


def _validate_recurring_time(value: str, name: str) -> str:
    if not isinstance(value, str) or not _RECURRING_TIME_RE.match(value):
        raise SmartRentValidationError("{} must be HH:MM or HH:MM:SS".format(name))
    return value


def build_create_guest_access_code_body(
    activation_type: str,
    first_name: str,
    last_name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    temporary_start_at: Optional[str] = None,
    temporary_end_at: Optional[str] = None,
    recurring_start_time: Optional[str] = None,
    recurring_end_time: Optional[str] = None,
    recurring_repeat_on: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    validate_activation_type(activation_type)
    _required_string(first_name, "first_name")
    _required_string(last_name, "last_name")
    _optional_nonempty_string(phone, "phone")
    _optional_nonempty_string(email, "email")
    if phone is None and email is None:
        raise SmartRentValidationError("at least one of phone or email is required")

    body: Dict[str, Any] = {
        "activation_type": activation_type,
        "first_name": first_name,
        "last_name": last_name,
    }
    if phone is not None:
        body["phone"] = phone
    if email is not None:
        body["email"] = email

    if activation_type == "temporary":
        if temporary_start_at is None or temporary_end_at is None:
            raise SmartRentValidationError(
                "temporary_start_at and temporary_end_at are required"
            )
        start_at, end_at = _validate_temporary_schedule(
            temporary_start_at, temporary_end_at
        )
        body["temporary_start_at"] = start_at
        body["temporary_end_at"] = end_at
    elif activation_type == "recurring":
        if (
            recurring_start_time is None
            or recurring_end_time is None
            or recurring_repeat_on is None
        ):
            raise SmartRentValidationError(
                "recurring_start_time, recurring_end_time, and "
                "recurring_repeat_on are required"
            )
        body["recurring_start_time"] = _validate_recurring_time(
            recurring_start_time, "recurring_start_time"
        )
        body["recurring_end_time"] = _validate_recurring_time(
            recurring_end_time, "recurring_end_time"
        )
        body["recurring_repeat_on"] = canonicalize_weekdays(recurring_repeat_on)

    return body


def build_update_guest_access_code_body(
    activation_type: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    temporary_start_at: Optional[str] = None,
    temporary_end_at: Optional[str] = None,
    recurring_start_time: Optional[str] = None,
    recurring_end_time: Optional[str] = None,
    recurring_repeat_on: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    if activation_type is not None:
        validate_activation_type(activation_type)
    _optional_nonempty_string(first_name, "first_name")
    _optional_nonempty_string(last_name, "last_name")
    _optional_nonempty_string(phone, "phone")
    _optional_nonempty_string(email, "email")

    body: Dict[str, Any] = {}
    optional_metadata = {
        "activation_type": activation_type,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "email": email,
    }
    for key, value in optional_metadata.items():
        if value is not None:
            body[key] = value

    has_temporary = temporary_start_at is not None or temporary_end_at is not None
    has_recurring = any(
        value is not None
        for value in (
            recurring_start_time,
            recurring_end_time,
            recurring_repeat_on,
        )
    )
    if has_temporary and has_recurring:
        raise SmartRentValidationError(
            "temporary and recurring schedules cannot be updated together"
        )
    if activation_type == "permanent" and (has_temporary or has_recurring):
        raise SmartRentValidationError("permanent access cannot include a schedule")
    if activation_type == "temporary" and has_recurring:
        raise SmartRentValidationError("temporary access cannot include recurrence")
    if activation_type == "recurring" and has_temporary:
        raise SmartRentValidationError(
            "recurring access cannot include temporary dates"
        )

    if has_temporary:
        if temporary_start_at is None or temporary_end_at is None:
            raise SmartRentValidationError(
                "temporary_start_at and temporary_end_at must be updated together"
            )
        start_at, end_at = _validate_temporary_schedule(
            temporary_start_at, temporary_end_at
        )
        body["temporary_start_at"] = start_at
        body["temporary_end_at"] = end_at

    if has_recurring:
        if (
            recurring_start_time is None
            or recurring_end_time is None
            or recurring_repeat_on is None
        ):
            raise SmartRentValidationError(
                "recurring_start_time, recurring_end_time, and "
                "recurring_repeat_on must be updated together"
            )
        body["recurring_start_time"] = _validate_recurring_time(
            recurring_start_time, "recurring_start_time"
        )
        body["recurring_end_time"] = _validate_recurring_time(
            recurring_end_time, "recurring_end_time"
        )
        body["recurring_repeat_on"] = canonicalize_weekdays(recurring_repeat_on)

    if not body:
        raise SmartRentValidationError("at least one update field is required")
    return body
