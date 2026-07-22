# auth/user_model.py
"""
Database models for the CampusMate AI authentication system.

This file lives inside the ``auth`` package (not at the project root)
to avoid any naming collision with the project's existing ML
structure — namely the top-level ``model.py`` (the PyTorch
``ChatbotModel`` class) and the ``models/`` folder (persisted
``.pth``/``.pkl`` artifacts). Keeping authentication code fully
isolated inside ``auth/`` makes that separation unambiguous.

This module defines the persistence layer for user accounts only.
It has no relationship whatsoever to the chatbot's data:

    * The chatbot's knowledge base lives in `data.csv` and is loaded by
      `utils.load_dataset()` — a flat file, read directly with pandas.
    * User accounts live in SQLite (`campusmate.db`) and are managed
      here via Flask-SQLAlchemy.

These two storage systems are intentionally kept independent. Nothing
in `chatbot.py` or `utils.py` reads from or writes to the database
defined here, and nothing here reads from `data.csv`.
"""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Centralised so every timestamp column in this module uses the same
    definition of "now" and nothing accidentally falls back to naive
    local time (a common source of subtle timezone bugs).
    """
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    """A registered CampusMate AI account.

    Supports three account types via ``user_type``:
        - "college_student" — uses college_name, department, semester
        - "school_student"  — uses school_name, class_level, stream
        - "parent"          — uses none of the above; just core fields

    Combines the fields required for authentication (email, password
    hash) with profile fields collected on the registration form. The
    college-specific and school-specific fields are all nullable at
    the database level, since only one set applies to any given user
    depending on ``user_type`` — which set is actually *required* for
    a given registration is enforced in ``auth/routes.py`` (via
    ``auth/validators.py``), not by a NOT NULL constraint here.

    Inherits from ``UserMixin`` (Flask-Login), which supplies default
    implementations of the four properties/methods Flask-Login needs
    to manage a logged-in session:

        - ``is_authenticated`` — True for any real, saved User instance
        - ``is_active``        — True unless we add account-disabling
                                  logic later (not in Phase 1 scope)
        - ``is_anonymous``     — False for real users
        - ``get_id()``         — returns ``str(self.id)``, which
                                  Flask-Login stores in the session and
                                  hands back to ``load_user`` (see the
                                  ``user_loader`` callback wired up in
                                  ``app.py``) to reload this object on
                                  each request.

    We do not override any of these — the defaults are correct for
    Phase 1 (no account suspension/banning yet).
    """

    __tablename__ = "users"

    # ------------------------------------------------------------------
    # Identity / authentication fields
    # ------------------------------------------------------------------
    id = db.Column(db.Integer, primary_key=True)

    # Indexed + unique: this is the login identifier, so every lookup
    # during login goes through this column. unique=True also creates
    # an implicit index on most backends, but we set index=True
    # explicitly for clarity and to guarantee it regardless of backend.
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Never store plaintext. Only the hash is persisted; see
    # set_password() / check_password() below. 255 chars comfortably
    # fits Werkzeug's default hash format (currently scrypt/pbkdf2
    # output), with headroom if the hashing method changes later.
    password_hash = db.Column(db.String(255), nullable=False)

    # ------------------------------------------------------------------
    # Account type — drives which profile fields below are relevant
    # ------------------------------------------------------------------
    # One of: "college_student", "school_student", "parent".
    # Indexed since future admin/reporting views will likely filter or
    # group users by type.
    user_type = db.Column(db.String(30), nullable=False, index=True)

    # ------------------------------------------------------------------
    # Profile fields (collected at registration)
    # ------------------------------------------------------------------
    full_name = db.Column(db.String(150), nullable=False)

    # Roll numbers only apply to college students. Nullable here since
    # school students and parents won't have one; unique=True still
    # holds — SQLite (and other major backends) allow multiple NULLs
    # in a unique column, since NULL is never considered equal to
    # another NULL.
    roll_number = db.Column(db.String(50), unique=True, nullable=True, index=True)

    # --- College-student fields (nullable — only required when
    #     user_type == "college_student"; enforced in auth/routes.py) ---
    department = db.Column(db.String(100), nullable=True)
    semester = db.Column(db.String(20), nullable=True)
    college_name = db.Column(db.String(200), nullable=True)

    # --- School-student fields (nullable — only required when
    #     user_type == "school_student"; enforced in auth/routes.py) ---
    school_name = db.Column(db.String(200), nullable=True)
    class_level = db.Column(db.String(20), nullable=True)   # e.g. "10th", "11th", "12th"
    stream = db.Column(db.String(50), nullable=True)        # e.g. "Science", "Commerce", "Arts"

    # Optional fields
    phone_number = db.Column(db.String(20), nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)  # stored file path/URL

    terms_accepted = db.Column(db.Boolean, nullable=False, default=False)

    # ------------------------------------------------------------------
    # Timestamps (UTC-aware)
    # ------------------------------------------------------------------
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<User id={self.id} email={self.email!r} roll_number={self.roll_number!r}>"

    # ------------------------------------------------------------------
    # Password handling
    # ------------------------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        """Hash ``raw_password`` and store it in ``password_hash``.

        Routes should call this instead of touching ``password_hash``
        or Werkzeug's hashing functions directly — keeping all hashing
        logic in one place makes it trivial to change the hashing
        method later without hunting through route code.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Return True if ``raw_password`` matches the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def record_login(self) -> None:
        """Update ``last_login`` to the current UTC time.

        Called by the login route right after a successful password
        check. Kept as a model method (rather than inline route code)
        so the "what counts as a login" definition lives in one place.
        """
        self.last_login = _utcnow()
