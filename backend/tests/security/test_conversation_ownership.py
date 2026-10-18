import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User, Conversation, ConversationMessage, AuditEvent, UserRole
from app.security import hash_password, create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_conversations():
    db: Session = SessionLocal()
    try:
        user_alice = db.query(User).filter(User.email == "alice_conv@camrail.net").first()
        if not user_alice:
            user_alice = User(
                email="alice_conv@camrail.net",
                password_hash=hash_password("alicepass"),
                full_name="Alice Conv",
                role=UserRole.READ_ONLY,
                department="Traction",
                is_active=True
            )
            db.add(user_alice)

        user_bob = db.query(User).filter(User.email == "bob_conv@camrail.net").first()
        if not user_bob:
            user_bob = User(
                email="bob_conv@camrail.net",
                password_hash=hash_password("bobpass"),
                full_name="Bob Conv",
                role=UserRole.READ_ONLY,
                department="Exploitation",
                is_active=True
            )
            db.add(user_bob)

        db.commit()

        # Alice's conversation
        conv_alice = Conversation(user_id=user_alice.id, title="Alice Secret Conversation")
        db.add(conv_alice)
        db.commit()
        db.refresh(conv_alice)

        msg_alice = ConversationMessage(
            conversation_id=conv_alice.id,
            role="user",
            content="Quelle est la procédure secrète ?"
        )
        db.add(msg_alice)
        db.commit()

        yield {
            "alice": user_alice,
            "bob": user_bob,
            "conv_alice": conv_alice
        }
    finally:
        db.close()


def test_user_cannot_read_others_conversation_messages(setup_conversations):
    data = setup_conversations
    alice = data["alice"]
    bob = data["bob"]
    conv_alice = data["conv_alice"]

    token_bob = create_access_token(bob.email, bob.role)
    token_alice = create_access_token(alice.email, alice.role)

    # Alice can read her own conversation messages -> 200
    res_alice = client.get(
        f"/assistant/conversations/{conv_alice.id}/messages",
        headers={"Authorization": f"Bearer {token_alice}"}
    )
    assert res_alice.status_code == 200
    assert len(res_alice.json()) >= 1

    # Bob attempts to read Alice's conversation -> 404 (Not 403, to protect existence)
    res_bob = client.get(
        f"/assistant/conversations/{conv_alice.id}/messages",
        headers={"Authorization": f"Bearer {token_bob}"}
    )
    assert res_bob.status_code == 404
    assert res_bob.json()["detail"] == "Conversation non trouvée"

    # Verify audit event "access_denied" is written
    db: Session = SessionLocal()
    try:
        denied = db.query(AuditEvent).filter(
            AuditEvent.actor_user_id == bob.id,
            AuditEvent.action == "access_denied",
            AuditEvent.entity_type == "conversation",
            AuditEvent.entity_id == str(conv_alice.id)
        ).first()
        assert denied is not None
    finally:
        db.close()


def test_user_cannot_delete_others_conversation(setup_conversations):
    data = setup_conversations
    bob = data["bob"]
    conv_alice = data["conv_alice"]

    token_bob = create_access_token(bob.email, bob.role)

    # Bob attempts to delete Alice's conversation -> 404
    res_delete = client.delete(
        f"/assistant/conversations/{conv_alice.id}",
        headers={"Authorization": f"Bearer {token_bob}"}
    )
    assert res_delete.status_code == 404
    assert res_delete.json()["detail"] == "Conversation non trouvée"

    # Verify conversation still exists
    db: Session = SessionLocal()
    try:
        check = db.query(Conversation).filter(Conversation.id == conv_alice.id).first()
        assert check is not None
    finally:
        db.close()


def test_user_cannot_append_message_to_others_conversation(setup_conversations):
    data = setup_conversations
    bob = data["bob"]
    conv_alice = data["conv_alice"]

    token_bob = create_access_token(bob.email, bob.role)

    # Bob attempts to send a question injecting into Alice's conversation ID -> 404
    res_query = client.post(
        "/assistant/query",
        headers={"Authorization": f"Bearer {token_bob}"},
        json={
            "query": "Tentative d'injection de message dans la conversation d'Alice",
            "conversation_id": conv_alice.id
        }
    )
    assert res_query.status_code == 404
    assert res_query.json()["detail"] == "Conversation non trouvée"

