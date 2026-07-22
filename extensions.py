# extensions.py
"""
Shared Flask extension instances.

This module exists purely to avoid circular imports between `app.py`,
`auth/user_model.py`, and `auth/routes.py`.

Without this file, a common pattern is:
    app.py       imports auth/user_model.py (to register the User model)
    auth/user_model.py imports db from app.py
    auth/routes.py imports db and User from app.py / auth/user_model.py
    app.py       imports auth/routes.py (to register the blueprint)

...which creates a circular import loop. By defining `db` and
`login_manager` here — with no dependency on `app.py` or `auth/user_model.py` —
every other module can safely import from `extensions` instead of
from each other.

Nothing in this file touches the chatbot, the ML model, or the CSV
dataset. It is purely infrastructure for the authentication system.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Single shared SQLAlchemy instance. Bound to the Flask app later via
# db.init_app(app) inside app.py — not created with an app here, so
# this file has zero dependency on app.py.
db = SQLAlchemy()

# Single shared LoginManager instance. Also bound later via
# login_manager.init_app(app) inside app.py.
login_manager = LoginManager()

# Where Flask-Login redirects unauthenticated users who hit a
# @login_required route. Points at the 'login' view inside the
# 'auth' blueprint (auth.login), which we'll implement in
# auth/routes.py.
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue to CampusMate AI."
login_manager.login_message_category = "info"

# "strong" session protection ties the session to the user's IP address
# and user-agent. If either changes mid-session, Flask-Login logs the
# user out and clears their remember-me cookie, guarding against
# session-cookie theft/replay. Safe default for this project; the main
# compatibility caveat is legitimate users on carrier-grade NAT or
# mobile networks that rotate IPs may get logged out more often than
# with "basic" protection.
login_manager.session_protection = "strong"
