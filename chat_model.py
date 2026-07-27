# chat_model.py
"""
Database models for CampusMate AI's persisted chat history.

This module is intentionally separate from ``auth/user_model.py`` (the
account/profile data) and from ``chatbot.py`` / ``utils.py`` (the
Gemini + dataset-retrieval logic). It only owns the *storage* of past
conversations so the "Recent Conversations" sidebar can be rebuilt on
every page load, on refresh, and after logging back in.

Two tables:

    ChatConversation
        One row per conversation thread for a given user. The sidebar
        title defaults to "New chat" the moment a conversation is
        created (never NULL), and is overwritten once with the first
        user question the first time a message is saved into it.

    ChatMessage
        One row per question/answer pair (not one row per chat
        "bubble" — a user question and the bot's answer that was
        generated for it are stored together, which keeps ordering
        trivial and matches how the frontend already renders pairs).

Both tables import ``db`` from ``extensions.py`` (not from
``auth/user_model.py`` or ``app.py``) to avoid circular imports, the
same pattern already used throughout the project. The foreign key to
the user table is declared by table name ("users.id") rather than by
importing the ``User`` class, so this module has zero import-time
dependency on ``auth/user_model.py``.
"""

from datetime import datetime, timezone

from extensions import db


def _utcnow() -> datetime:
    """Timezone-aware UTC "now", consistent with auth/user_model.py."""
    return datetime.now(timezone.utc)


def _default_title() -> str:
    """Default sidebar label for a brand-new conversation. Kept as a
    function (rather than a bare string default) purely for symmetry
    with ``_utcnow`` and so it's trivial to change in one place.
    """
    return "New chat"


class ChatConversation(db.Model):
    """A single chat thread belonging to one user.

    ``messages`` is declared ``lazy="dynamic"`` so callers can further
    filter/order it as a query (e.g. ``conversation.messages.order_by(...)``)
    instead of always loading every message whenever a conversation is
    touched.

    ``cascade="all, delete-orphan"`` means deleting a ``ChatConversation``
    (via ``db.session.delete(conversation)``) also deletes every
    ``ChatMessage`` that belongs to it — required for the "Delete should
    remove only the selected conversation" and "Clear History" features
    to fully clean up, without leaving orphaned message rows behind.
    """

    __tablename__ = "chat_conversations"

    id = db.Column(db.Integer, primary_key=True)

    # Indexed: every history/list query filters by the logged-in user.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Sidebar label. Defaults to "New chat" (never NULL) the moment a
    # conversation row is created. The /chat route overwrites this once,
    # the first time a message is saved into the conversation, with the
    # first user question (truncated) — see app.py's check for both
    # "no title yet" and "still the default" before overwriting.
    title = db.Column(db.String(150), nullable=False, default=_default_title)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    # Bumped every time a message is saved into this conversation, and
    # used to sort the sidebar so the most recently active thread
    # floats to the top (matches common chat-app behaviour).
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    messages = db.relationship(
        "ChatMessage",
        backref="conversation",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )

    # Forces SQLite's real AUTOINCREMENT behaviour (backed by the
    # internal sqlite_sequence table) instead of a bare rowid alias.
    # Conversations are routinely deleted (delete_conversation,
    # clear_chat_history), and a bare rowid alias is free to reuse the
    # highest id that ever existed once the row using it is gone;
    # AUTOINCREMENT guarantees a new conversation never gets an id that
    # was already used before, even after deletes.
    __table_args__ = {"sqlite_autoincrement": True}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<ChatConversation id={self.id} user_id={self.user_id} title={self.title!r}>"

    def to_summary_dict(self) -> dict:
        """Lightweight summary used anywhere the full message list isn't
        needed. ``chat_history`` in app.py builds its own richer payload,
        but this keeps a single, trustworthy source for the "title is
        never empty" guarantee if other routes need it later.
        """
        return {
            "conversation_id": self.id,
            "title": self.title or _default_title(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ChatMessage(db.Model):
    """One question/answer pair inside a conversation.

    ``client_id`` is an opaque token the frontend generates once per
    send (``crypto.randomUUID()``) and resubmits with the request. If
    a message with the same ``(conversation_id, client_id)`` already
    exists — e.g. a double-click on Send, or a retried fetch after a
    flaky connection — the backend returns the already-saved answer
    instead of creating a second row. This is what keeps a slow
    network or an accidental double submit from producing duplicate
    messages in history.
    """

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

    # Free-form label surfaced in the UI (e.g. "Gemini", "Dataset
    # match", an intent name, ...) — whatever chatbot.answer_question()
    # reports back, if anything. Nullable since not every answer path
    # necessarily sets one.
    source = db.Column(db.String(120), nullable=True)

    client_id = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint("conversation_id", "client_id", name="uq_chat_message_conversation_client"),
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<ChatMessage id={self.id} conversation_id={self.conversation_id}>"

    def to_dict(self) -> dict:
        """JSON-serialisable representation used by /chat/history."""
        return {
            "question": self.question,
            "answer": self.answer,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }
