# app.py
"""Flask entry point for CampusMate AI.

This application serves both the authentication portal and the chatbot.
The authentication system is isolated in ``auth/`` and uses Flask-Login
and SQLAlchemy through ``extensions.py``.
"""

import os
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from chatbot import Chatbot
from config import get_config
from extensions import db, login_manager
from auth.routes import auth_bp
from auth.user_model import User
from chat_model import ChatConversation, ChatMessage
from db_migrate import sync_schema

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

# Build the database tables if needed, then reconcile any columns/indexes
# that a pre-existing database file is missing (e.g. an older database
# created before `client_id` existed on ChatMessage, or a primary key
# that isn't wired up as a proper SQLite rowid alias). See db_migrate.py
# for exactly what this does and why create_all() alone isn't enough.
with app.app_context():
    db.create_all()
    sync_schema(app, db)

# Initialize the chatbot after auth setup so startup stays fast.
chatbot = Chatbot()


# ---------------------------------------------------------------------------
# Chat history helpers
# ---------------------------------------------------------------------------
class ConversationPersistenceError(Exception):
    """Raised whenever a conversation or message fails to save.

    Every route that touches ChatConversation/ChatMessage catches this
    specifically (instead of letting a raw SQLAlchemyError/Exception
    escape) so the client always gets a clean JSON error instead of
    Flask's default HTML 500 page.
    """


def _get_or_create_empty_conversation():
    """Return an existing empty conversation for the current user, or make one.

    "Empty" means no ChatMessage rows have been saved into it yet. Reusing
    an existing empty conversation (instead of always inserting a new row)
    is what stops repeated "New Chat" clicks — or a page reload before the
    user has typed anything — from littering the sidebar with duplicate
    blank conversations.

    Every new conversation gets ``title="New chat"`` explicitly (in
    addition to the model's own default — see chat_model.py) so a
    conversation row is never persisted with a NULL title, and the
    freshly committed row is re-fetched to confirm SQLite actually
    assigned it a real integer id before handing it back to the caller.
    """
    try:
        existing_empty = (
            ChatConversation.query
            .filter_by(user_id=current_user.id)
            .filter(~ChatConversation.messages.any())
            .order_by(ChatConversation.created_at.desc())
            .first()
        )
        if existing_empty:
            return existing_empty

        conversation = ChatConversation(user_id=current_user.id, title="New chat")
        db.session.add(conversation)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to create a new conversation for user %s", current_user.id)
        raise ConversationPersistenceError("Could not create a new conversation.")

    if conversation.id is None:
        # Defensive: should be unreachable after a successful commit, but
        # this is exactly the failure mode db_migrate.py's primary-key
        # repair exists to prevent (a broken rowid alias silently letting
        # a NULL-id row through). Fail loudly and specifically instead of
        # returning a conversation the rest of the app can't use.
        db.session.rollback()
        logger.error("Conversation committed without an id for user %s", current_user.id)
        raise ConversationPersistenceError(
            "Conversation was saved without a valid id. The database schema "
            "may need repair; check server logs for primary-key warnings."
        )

    return conversation


def _resolve_conversation(raw_conversation_id):
    """Resolve a conversation_id from a request into a ChatConversation owned
    by the current user.

    Returns None if a conversation_id was supplied but doesn't exist / isn't
    owned by this user (the caller should respond 404). If no
    conversation_id was supplied at all, falls back to
    ``_get_or_create_empty_conversation`` so older clients (or the JSON
    /predict-style callers) that don't yet send one still work.

    Raises ConversationPersistenceError if the lookup itself fails (e.g.
    a DB-level error), so the caller never lets a raw exception escape.
    """
    if not raw_conversation_id:
        return _get_or_create_empty_conversation()

    try:
        conversation_id = int(raw_conversation_id)
    except (TypeError, ValueError):
        return None

    try:
        return ChatConversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to resolve conversation_id=%s", raw_conversation_id)
        raise ConversationPersistenceError("Could not look up the conversation.")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@app.errorhandler(ConversationPersistenceError)
def handle_conversation_persistence_error(exc):
    return jsonify({"error": str(exc)}), 500


@app.errorhandler(500)
def handle_internal_error(exc):
    # Safety net: if anything else ever raises unhandled inside a route,
    # the client still gets JSON back instead of Flask's default HTML
    # error page (which is what a plain, un-caught exception would
    # otherwise produce for API callers).
    logger.exception("Unhandled server error")
    return jsonify({"error": "Internal server error."}), 500


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
    return render_template('index.html', user=current_user)


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
    if request.is_json:
        data = request.get_json(force=True)
        question = (data or {}).get('question')
        uploaded_files = []
        raw_conversation_id = (data or {}).get('conversation_id')
        client_id = (data or {}).get('client_id')
    else:
        question = request.form.get('question')
        uploaded_files = list(request.files.getlist('files'))
        raw_conversation_id = request.form.get('conversation_id')
        client_id = request.form.get('client_id')

    if not question:
        logger.warning("Invalid request payload: %s", request.get_data(as_text=True))
        return jsonify({"error": "Missing 'question' field in the request."}), 400

    try:
        conversation = _resolve_conversation(raw_conversation_id)
    except ConversationPersistenceError as exc:
        return jsonify({"error": str(exc)}), 500

    if conversation is None:
        return jsonify({"error": "Conversation not found."}), 404

    # Idempotency: if the frontend resubmitted the same client_id (double
    # click, retried fetch after a flaky connection, etc.) for this
    # conversation, return the answer that was already saved instead of
    # generating and storing a duplicate message.
    if client_id:
        try:
            existing_message = ChatMessage.query.filter_by(
                conversation_id=conversation.id, client_id=client_id
            ).first()
        except SQLAlchemyError:
            db.session.rollback()
            logger.exception("Failed to check for an existing message with client_id=%s", client_id)
            existing_message = None
        if existing_message:
            return jsonify({
                "answer": existing_message.answer,
                "source": existing_message.source,
                "conversation_id": conversation.id,
            })

    logger.info("Chat request: %s", question)
    try:
        response = chatbot.answer_question(question, uploaded_files=uploaded_files)
    except Exception as exc:
        logger.exception("Chat prediction error: %s", exc)
        return jsonify({"error": "Internal server error during prediction."}), 500

    response_payload = dict(response) if isinstance(response, dict) else {"answer": str(response)}
    answer_text = response_payload.get('answer', '')
    source = response_payload.get('source') or response_payload.get('intent')

    # Fields here are kept in exact lockstep with chat_model.ChatMessage's
    # columns: conversation_id, question, answer, source, client_id.
    try:
        message = ChatMessage(
            conversation_id=conversation.id,
            question=question,
            answer=answer_text,
            source=source,
            client_id=client_id or None,
        )
        db.session.add(message)
        # "New chat" is the model's own default (see chat_model.py), so an
        # untouched conversation's title is always exactly that string
        # until the first message names it — check for both "no title at
        # all" (defensive, for rows from older code paths) and "still the
        # placeholder default" before overwriting.
        if not conversation.title or conversation.title == "New chat":
            conversation.title = question[:120]
        conversation.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    except SQLAlchemyError:
        # A concurrent duplicate request racing on the same client_id will
        # trip the unique constraint here; roll back and return the row
        # that won the race instead of surfacing a 500 to the user.
        db.session.rollback()
        if client_id:
            try:
                existing_message = ChatMessage.query.filter_by(
                    conversation_id=conversation.id, client_id=client_id
                ).first()
            except SQLAlchemyError:
                db.session.rollback()
                existing_message = None
            if existing_message:
                return jsonify({
                    "answer": existing_message.answer,
                    "source": existing_message.source,
                    "conversation_id": conversation.id,
                })
        logger.exception("Failed to persist chat message for conversation %s", conversation.id)
        return jsonify({"error": "Internal server error while saving the conversation."}), 500

    if message.id is None:
        # Same defensive check as _get_or_create_empty_conversation: a
        # commit that "succeeds" but leaves id unset means the table's
        # primary key isn't wired up as a rowid alias. Surface this
        # clearly rather than returning a message the client can't
        # reliably reference (e.g. for future edit/delete features).
        logger.error("ChatMessage committed without an id for conversation %s", conversation.id)
        return jsonify({"error": "Message was saved without a valid id."}), 500

    response_payload['conversation_id'] = conversation.id
    return jsonify(response_payload)


@app.route('/chat/new', methods=['POST'])
@login_required
def new_chat():
    """Start a new conversation without deleting any previous ones.

    Reuses an already-empty conversation if the user has one (see
    ``_get_or_create_empty_conversation``), so repeated "New Chat" clicks
    don't create empty duplicate threads in the sidebar.
    """
    try:
        conversation = _get_or_create_empty_conversation()
    except ConversationPersistenceError as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"conversation_id": conversation.id, "title": conversation.title})


@app.route('/chat/history', methods=['GET'])
@login_required
def chat_history():
    """List every conversation belonging to the logged-in user, most
    recently active first, each with its full message history in
    chronological order."""
    try:
        conversations = (
            ChatConversation.query
            .filter_by(user_id=current_user.id)
            .order_by(ChatConversation.updated_at.desc())
            .all()
        )

        payload = []
        for conversation in conversations:
            messages = conversation.messages.order_by(ChatMessage.created_at.asc()).all()
            title = conversation.title or "New chat"
            payload.append({
                "conversation_id": conversation.id,
                "title": title,
                "message_count": len(messages),
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "messages": [m.to_dict() for m in messages],
            })
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to load chat history for user %s", current_user.id)
        return jsonify({"error": "Could not load chat history."}), 500

    return jsonify({"conversations": payload})


@app.route('/chat/history/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete exactly one conversation (and its messages) for this user."""
    try:
        conversation = ChatConversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first()
        if not conversation:
            return jsonify({"error": "Conversation not found."}), 404

        db.session.delete(conversation)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to delete conversation %s", conversation_id)
        return jsonify({"error": "Could not delete conversation."}), 500

    return jsonify({"status": "ok"})


@app.route('/chat/history', methods=['DELETE'])
@login_required
def clear_chat_history():
    """Delete every conversation belonging to the logged-in user only."""
    try:
        conversations = ChatConversation.query.filter_by(user_id=current_user.id).all()
        for conversation in conversations:
            db.session.delete(conversation)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to clear chat history for user %s", current_user.id)
        return jsonify({"error": "Could not clear chat history."}), 500

    return jsonify({"status": "ok"})


# Debug route list when the app starts.
for rule in app.url_map.iter_rules():
    logger.info('Registered route: %s', rule)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info("Starting Flask server on port %s", port)
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
