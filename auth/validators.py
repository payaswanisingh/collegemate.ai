# auth/validators.py
"""
Reusable input validators for the authentication system.

This file lives inside the ``auth`` package to keep all
authentication-related code (models, validators, routes) isolated
from the project's existing ML structure (``model.py``, ``models/``,
``chatbot.py``, ``utils.py``, ``data.csv``), none of which this
module touches or depends on.

This module has no dependency on Flask, SQLAlchemy, or the `User`
model — it is pure, framework-agnostic validation logic. Each
function inspects a single piece of input and returns either:

    * ``None``          — the input is valid, or
    * ``str``           — a short, user-facing error message
                           explaining why it is invalid.

Keeping validation here (rather than in `auth/user_model.py` or inline in
`auth/routes.py`) means:

    * `auth/user_model.py` stays focused on persistence and password hashing
      only (no validation rules baked into the model).
    * `forms.py` can compose these functions to validate a whole
      submitted form and collect per-field errors.
    * `auth/routes.py` stays focused on request handling and control
      flow — it will call into `forms.py`, not these validators,
      directly.

None of these functions touch the database, so they never need an
application or request context and can be unit-tested in isolation.
"""

import re
from typing import Optional

from email_validator import validate_email as _validate_email_syntax
from email_validator import EmailNotValidError


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
def validate_email(email: str) -> Optional[str]:
    """Validate an email address's syntax.

    Uses the ``email-validator`` library (already in requirements.txt)
    rather than a hand-rolled regex, since correctly validating email
    syntax per RFC rules is notoriously easy to get subtly wrong with
    regex alone.

    Note: this checks syntax only. It does NOT check whether the
    address is already registered — that is a database concern and
    belongs in ``auth/routes.py`` (checking ``User.query`` /
    ``db.session.get``), not in this framework-agnostic module.

    Returns ``None`` if valid, or an error message string if not.
    """
    if not email or not email.strip():
        return "Email is required."

    try:
        # check_deliverability=False keeps this a pure syntax check and
        # avoids making a DNS lookup during form validation (which would
        # add latency and an external network dependency to every
        # registration/login attempt).
        _validate_email_syntax(email.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        return f"Enter a valid email address ({exc})."

    return None


# ---------------------------------------------------------------------------
# Password strength
# ---------------------------------------------------------------------------
_MIN_PASSWORD_LENGTH = 8
_MAX_PASSWORD_LENGTH = 128

_UPPERCASE_RE = re.compile(r"[A-Z]")
_LOWERCASE_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_CHAR_RE = re.compile(r"[^\w\s]")  # punctuation/symbols


def validate_password_strength(password: str) -> Optional[str]:
    """Validate password strength.

    Requires at minimum:
        - between 8 and 128 characters
        - at least one uppercase letter
        - at least one lowercase letter
        - at least one digit
        - at least one special character (punctuation/symbol)

    This function only judges strength — it never hashes, stores, or
    compares the password. Hashing/verification stays entirely inside
    ``User.set_password`` / ``User.check_password`` in ``auth/user_model.py``.

    Returns ``None`` if valid, or an error message string if not.
    """
    if not password:
        return "Password is required."

    if len(password) < _MIN_PASSWORD_LENGTH:
        return f"Password must be at least {_MIN_PASSWORD_LENGTH} characters long."

    if len(password) > _MAX_PASSWORD_LENGTH:
        return f"Password must be no more than {_MAX_PASSWORD_LENGTH} characters long."

    if not _UPPERCASE_RE.search(password):
        return "Password must contain at least one uppercase letter."

    if not _LOWERCASE_RE.search(password):
        return "Password must contain at least one lowercase letter."

    if not _DIGIT_RE.search(password):
        return "Password must contain at least one number."

    if not _SPECIAL_CHAR_RE.search(password):
        return "Password must contain at least one special character."

    return None


def validate_password_confirmation(password: str, confirm_password: str) -> Optional[str]:
    """Validate that a confirmation field matches the original password.

    Kept separate from ``validate_password_strength`` so each function
    checks exactly one thing and callers can decide whether to run
    both (e.g. registration) or only the strength check (e.g. a future
    "change password" flow with no confirmation field).

    Returns ``None`` if valid, or an error message string if not.
    """
    if not confirm_password:
        return "Please confirm your password."

    if password != confirm_password:
        return "Passwords do not match."

    return None


# ---------------------------------------------------------------------------
# Roll number
# ---------------------------------------------------------------------------
# Alphanumeric, may include hyphens or slashes (common in roll-number
# formats like "CS21B045" or "2021/CS/045"), 4-20 characters long.
_ROLL_NUMBER_RE = re.compile(r"^[A-Za-z0-9/\-]{4,20}$")


def validate_roll_number(roll_number: str) -> Optional[str]:
    """Validate a student roll number's format.

    Accepts letters, digits, hyphens, and forward slashes, 4-20
    characters long — broad enough to cover common institutional
    formats (e.g. ``CS21B045``, ``2021/CS/045``) without assuming one
    specific college's exact scheme.

    This checks format only, not uniqueness — uniqueness is enforced
    by the database's unique constraint on ``User.roll_number`` (see
    ``auth/user_model.py``) and should be checked against the database inside
    ``auth/routes.py``.

    Returns ``None`` if valid, or an error message string if not.
    """
    if not roll_number or not roll_number.strip():
        return "Roll number is required."

    if not _ROLL_NUMBER_RE.match(roll_number.strip()):
        return (
            "Roll number must be 4-20 characters long and contain only "
            "letters, numbers, hyphens, or slashes."
        )

    return None


# ---------------------------------------------------------------------------
# Phone number (optional field)
# ---------------------------------------------------------------------------
# Optional leading '+', then 7-15 digits — a permissive superset of
# most national phone number lengths (E.164 allows up to 15 digits).
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def validate_phone_number(phone_number: Optional[str], required: bool = False) -> Optional[str]:
    """Validate a phone number's format.

    ``required`` controls whether an empty value is an error. CampusMate AI
    requires a phone number for every account type, so callers pass
    ``required=True``; keep the default ``False`` for any future flow
    where it really is optional.

    Accepts an optional leading ``+`` followed by 7-15 digits (no
    spaces, dashes, or parentheses) — callers/forms are expected to
    strip formatting characters before calling this, or a future
    iteration can normalise input before validation.

    Returns ``None`` if valid, or an error message string if not.
    """
    if not phone_number or not phone_number.strip():
        return "Phone number is required." if required else None

    if not _PHONE_RE.match(phone_number.strip()):
        return "Enter a valid phone number (7-15 digits, optionally starting with +)."

    return None


# ---------------------------------------------------------------------------
# User type / school-specific fields
# ---------------------------------------------------------------------------
VALID_USER_TYPES = ("college_student", "school_student", "parent")
VALID_CLASS_LEVELS = ("6", "7", "8", "9", "10", "11", "12")
VALID_STREAMS = ("Science", "Commerce", "Arts")


def validate_user_type(user_type: Optional[str]) -> Optional[str]:
    """Validate the selected account type."""
    if not user_type or not user_type.strip():
        return "Please select an account type."
    if user_type not in VALID_USER_TYPES:
        return "Invalid account type selected."
    return None


def validate_class_level(class_level: Optional[str]) -> Optional[str]:
    """Validate a school student's class (6-12). Required for school students."""
    if not class_level or not class_level.strip():
        return "Class is required."
    if class_level.strip() not in VALID_CLASS_LEVELS:
        return "Please select a valid class (6-12)."
    return None


def validate_stream(stream: Optional[str], class_level: Optional[str]) -> Optional[str]:
    """Validate stream — only required/checked for class 11 and 12.

    For classes 6-10, ``stream`` is not applicable; this function only
    enforces the rule when ``class_level`` is 11 or 12.
    """
    if class_level not in ("11", "12"):
        return None
    if not stream or not stream.strip():
        return "Stream is required for class 11 and 12."
    if stream.strip() not in VALID_STREAMS:
        return "Please select a valid stream (Science, Commerce, or Arts)."
    return None


# ---------------------------------------------------------------------------
# Required-text helper (name, department, semester, college name, etc.)
# ---------------------------------------------------------------------------
def validate_required_text(value: Optional[str], field_label: str, max_length: int = 200) -> Optional[str]:
    """Validate that a plain required text field is present and within length.

    Generic helper for simple required string fields (full name,
    department, semester, college name) that don't need a dedicated
    regex — keeps ``forms.py`` from repeating the same "is it empty /
    is it too long" checks for every plain text field.

    Returns ``None`` if valid, or an error message string if not.
    """
    if not value or not value.strip():
        return f"{field_label} is required."

    if len(value.strip()) > max_length:
        return f"{field_label} must be no more than {max_length} characters long."

    return None


def validate_terms_accepted(terms_accepted: bool) -> Optional[str]:
    """Validate that the terms-and-conditions checkbox was accepted.

    Returns ``None`` if valid, or an error message string if not.
    """
    if not terms_accepted:
        return "You must accept the terms and conditions to register."

    return None
