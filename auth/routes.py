# auth/routes.py
"""
Authentication routes for CampusMate AI: register, login, logout.

This Blueprint is completely separate from the chatbot. It has no
import of, or dependency on, ``chatbot.py``, ``model.py``, ``utils.py``,
``models/`` (the ML artifacts folder), or ``data.csv``. Those files are
not touched by anything in this module.

Imports used here:
    - ``extensions``          -> shared ``db`` (SQLAlchemy) instance
    - ``auth.user_model``     -> the ``User`` model
    - ``auth.validators``     -> framework-agnostic field validators
    - ``flask_login``         -> ``login_user``, ``logout_user``,
                                  ``login_required``, ``current_user``

Routes are kept intentionally "thin": they handle the HTTP request/
response cycle and orchestrate calls to the validator functions and
the ``User`` model, but contain no validation rules or password-hashing
logic themselves — that logic lives in ``auth/validators.py`` and
``auth/user_model.py`` respectively.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from auth.user_model import User
from auth.validators import (
    validate_email,
    validate_password_strength,
    validate_password_confirmation,
    validate_roll_number,
    validate_phone_number,
    validate_required_text,
    validate_terms_accepted,
    validate_user_type,
    validate_class_level,
    validate_stream,
)

# Blueprint name is "auth" — this must match the string used in
# extensions.py's `login_manager.login_view = "auth.login"`, since
# Flask-Login builds that redirect target as "<blueprint_name>.<view_name>".
auth_bp = Blueprint("auth", __name__, template_folder="../templates")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle new student account creation.

    GET  -> render the registration form.
    POST -> validate submitted fields, check for duplicate email/roll
            number, create the User, hash the password, log the user
            in, and redirect to the dashboard.
    """
    # Already-logged-in users don't need to register again.
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "GET":
        return render_template("register.html")

    # ------------------------------------------------------------------
    # Collect submitted form fields
    # ------------------------------------------------------------------
    # .strip() on text fields to avoid storing/comparing accidental
    # leading/trailing whitespace from the form.
    user_type = (request.form.get("user_type") or "").strip()
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""
    phone_number = (request.form.get("phone_number") or "").strip() or None
    # Checkbox fields only appear in form data when checked.
    terms_accepted = request.form.get("terms_accepted") == "on"

    # Type-specific fields. Only the ones relevant to `user_type` are
    # validated/persisted below; the rest are left as None.
    roll_number = (request.form.get("roll_number") or "").strip()
    department = (request.form.get("department") or "").strip()
    semester = (request.form.get("semester") or "").strip()
    college_name = (request.form.get("college_name") or "").strip()

    school_name = (request.form.get("school_name") or "").strip()
    class_level = (request.form.get("class_level") or "").strip()
    stream = (request.form.get("stream") or "").strip()

    # ------------------------------------------------------------------
    # Common fields, required for every account type.
    # ------------------------------------------------------------------
    errors = []
    for error in (
        validate_user_type(user_type),
        validate_required_text(full_name, "Full name", max_length=150),
        validate_email(email),
        validate_password_strength(password),
        validate_password_confirmation(password, confirm_password),
        validate_phone_number(phone_number, required=True),
        validate_terms_accepted(terms_accepted),
    ):
        if error:
            errors.append(error)

    # ------------------------------------------------------------------
    # Type-specific fields. Skipped entirely if user_type itself was
    # invalid/missing, since we wouldn't know which set to check.
    # ------------------------------------------------------------------
    if user_type == "college_student":
        for error in (
            validate_roll_number(roll_number),
            validate_required_text(department, "Department", max_length=100),
            validate_required_text(semester, "Semester", max_length=20),
            validate_required_text(college_name, "College name", max_length=200),
        ):
            if error:
                errors.append(error)
        # Fields that don't apply to this type are cleared so they never
        # get persisted accidentally.
        school_name = class_level = stream = None

    elif user_type == "school_student":
        for error in (
            validate_required_text(school_name, "School name", max_length=200),
            validate_class_level(class_level),
        ):
            if error:
                errors.append(error)
        # Stream is only required/checked for class 11 and 12.
        stream_error = validate_stream(stream, class_level)
        if stream_error:
            errors.append(stream_error)
        if class_level not in ("11", "12"):
            stream = None
        roll_number = department = semester = college_name = None

    elif user_type == "parent":
        roll_number = department = semester = college_name = None
        school_name = class_level = stream = None
    # else: user_type was invalid — validate_user_type() already added the error.

    # ------------------------------------------------------------------
    # Duplicate checks — these need the database, so they live here in
    # the route rather than in the framework-agnostic validators module.
    # ------------------------------------------------------------------
    if not errors:
        if User.query.filter_by(email=email).first() is not None:
            errors.append("An account with this email already exists.")

        if roll_number and User.query.filter_by(roll_number=roll_number).first() is not None:
            errors.append("An account with this roll number already exists.")

    if errors:
        for error in errors:
            flash(error, "danger")
        # Re-render the form with the errors; re-populate everything
        # the student already typed EXCEPT the passwords, so they don't
        # have to retype the rest of the form.
        return render_template(
            "register.html",
            user_type=user_type,
            full_name=full_name,
            email=email,
            phone_number=phone_number or "",
            roll_number=roll_number or "",
            department=department or "",
            semester=semester or "",
            college_name=college_name or "",
            school_name=school_name or "",
            class_level=class_level or "",
            stream=stream or "",
        )

    # ------------------------------------------------------------------
    # All validation passed — create and persist the new user.
    # ------------------------------------------------------------------
    new_user = User(
        user_type=user_type,
        full_name=full_name,
        email=email,
        roll_number=roll_number or None,
        department=department or None,
        semester=semester or None,
        college_name=college_name or None,
        school_name=school_name or None,
        class_level=class_level or None,
        stream=stream or None,
        phone_number=phone_number,
        terms_accepted=terms_accepted,
    )
    # Hashing happens inside the model — the raw password is never
    # assigned to any column directly.
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception:
        # Roll back so a failed insert (e.g. a race-condition duplicate,
        # or a transient DB error) never leaves the session in a broken
        # half-committed state for the next request.
        db.session.rollback()
        flash("Something went wrong while creating your account. Please try again.", "danger")
        return render_template(
            "register.html",
            user_type=user_type,
            full_name=full_name,
            email=email,
            phone_number=phone_number or "",
            roll_number=roll_number or "",
            department=department or "",
            semester=semester or "",
            college_name=college_name or "",
            school_name=school_name or "",
            class_level=class_level or "",
            stream=stream or "",
        )

    # Registration implies an immediate, trusted login — no separate
    # password check needed since we just created this exact user.
    login_user(new_user)
    flash(f"Welcome to CampusMate AI, {new_user.full_name}!", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle existing user login.

    GET  -> render the login form.
    POST -> look up the user by email, verify the password, update
            last_login, log the user in, and redirect to the dashboard.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    # Basic presence check before hitting the database at all.
    if not email or not password:
        flash("Please enter both email and password.", "danger")
        return render_template("login.html", email=email)

    user = User.query.filter_by(email=email).first()

    # Deliberately use the SAME error message whether the email doesn't
    # exist or the password is wrong. Revealing "no account with that
    # email" vs "wrong password" separately lets an attacker enumerate
    # which emails are registered — a well-known login-security pitfall.
    invalid_credentials_message = "Incorrect email or password."

    if user is None or not user.check_password(password):
        flash(invalid_credentials_message, "danger")
        return render_template("login.html", email=email)

    # Password verified — record the login time and persist it.
    user.record_login()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # A failure to record last_login is not a reason to block the
        # student from logging in — log them in anyway and move on.
        # (No chatbot data is touched here regardless of outcome.)

    login_user(user)
    flash(f"Welcome back, {user.full_name}!", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    """Log the current user out and return them to the landing page."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing"))
