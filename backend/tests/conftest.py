import pytest
from app.database import SessionLocal, Base, engine

@pytest.fixture(scope="session")
def db_engine():
    # En environnement de test, on pourrait utiliser une DB séparée
    # Mais ici on garde l'engine standard par simplicité
    yield engine

@pytest.fixture(scope="function")
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def reset_login_attempts_between_tests():
    """Évite qu'un test de bruteforce ne verrouille les comptes de test pour les tests suivants."""
    from app.models.schemas import LoginAttempt, User
    with SessionLocal() as s:
        s.query(LoginAttempt).delete()
        s.query(User).filter(User.email.in_(["admin@camrail.net", "docadmin@camrail.net", "readonly@camrail.net"])).update({"is_active": True})
        s.commit()
    yield
    with SessionLocal() as s:
        s.query(LoginAttempt).delete()
        s.query(User).filter(User.email.in_(["admin@camrail.net", "docadmin@camrail.net", "readonly@camrail.net"])).update({"is_active": True})
        s.commit()


