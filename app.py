# app.py
"""Flask entry point for CampusMate AI.

This application serves both the authentication portal and the chatbot.
The authentication system is isolated in ``auth/`` and uses Flask-Login
and SQLAlchemy through ``extensions.py``.
"""

import os
import logging
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from flask_login import login_required, current_user

from chatbot import Chatbot
from config import get_config
from extensions import db, login_manager
from auth.routes import auth_bp
from auth.user_model import User

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------------------
app = Flask(__name__, instance_relative_config=True)
app.config.from_object(get_config())

# Ensure the instance folder exists for the SQLite database file.
os.makedirs(app.instance_path, exist_ok=True)

CORS(app)
db.init_app(app)
login_manager.init_app(app)

# Register authentication blueprint.
app.register_blueprint(auth_bp)

# Flask-Login user loader.
@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    return User.query.get(int(user_id))

# Build the database tables if needed.
with app.app_context():
    db.create_all()

# Initialize the chatbot after auth setup so startup stays fast.
chatbot = Chatbot()

# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
@app.route('/', methods=['GET'])
@app.route('/landing', methods=['GET'])
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


@app.route('/app', methods=['GET'])
@login_required
def chatbot_page():
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})


@app.route('/predict', methods=['POST'])
@login_required
def predict_legacy():
    data = request.get_json(force=True)
    if not data or 'question' not in data:
        logger.warning("Invalid request payload: %s", data)
        return jsonify({"error": "Missing 'question' field in JSON payload."}), 400
    question = data['question']
    logger.info("Legacy predict request: %s", question)
    result = chatbot.predict(question)
    return jsonify({"intent": result.get('intent')})


@app.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json(force=True)
    if not data or 'question' not in data:
        logger.warning("Invalid request payload: %s", data)
        return jsonify({"error": "Missing 'question' field in JSON payload."}), 400

    question = data['question']
    logger.info("Chat request: %s", question)
    try:
        response = chatbot.predict(question)
        return jsonify(response)
    except Exception as exc:
        logger.exception("Chat prediction error: %s", exc)
        return jsonify({"error": "Internal server error during prediction."}), 500


# Debug route list when the app starts.
for rule in app.url_map.iter_rules():
    logger.info('Registered route: %s', rule)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info("Starting Flask server on port %s", port)
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
