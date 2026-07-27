import uuid
from app import app, db
from auth.user_model import ChatConversation

app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/test_chatbot.db"

with app.app_context():
    db.drop_all()
    db.create_all()

client = app.test_client()
email = f"{uuid.uuid4().hex[:8]}@campusmate.ai"
password = "secret123"

register_response = client.post("/register", json={
    "full_name": "Campus Test User",
    "email": email,
    "password": password,
})
print("REGISTER", register_response.status_code, register_response.get_json())

login_response = client.post("/login", json={
    "email": email,
    "password": password,
})
print("LOGIN", login_response.status_code, login_response.get_json())

chat_response = client.post("/chat", json={
    "question": "What is the admission process?",
    "conversation_id": "conv-smoke-test",
})
print("CHAT", chat_response.status_code, chat_response.get_json())

history_response = client.get("/chat/history")
print("HISTORY", history_response.status_code, history_response.get_json())

conversation = ChatConversation.query.filter_by(id="conv-smoke-test").first()
print("CONV_EXISTS", conversation is not None)
print("MESSAGE_COUNT", len(conversation.messages) if conversation else 0)
