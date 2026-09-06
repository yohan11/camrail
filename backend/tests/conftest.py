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
