# auth/__init__.py
"""
The ``auth`` package holds everything related to user authentication:
the ``User`` model, input validators, and the Flask Blueprint with the
register/login/logout routes.

This package is intentionally self-contained and has no dependency on
the chatbot's ML pipeline (``model.py``, ``models/``, ``chatbot.py``,
``utils.py``, ``data.csv``). Nothing in those files imports from here,
and nothing here imports from those files.

The Blueprint object itself (``auth_bp``) is defined in
``auth/routes.py``. It is not re-exported here to keep this file
minimal — ``app.py`` will import it directly:

    from auth.routes import auth_bp
    app.register_blueprint(auth_bp)
"""
