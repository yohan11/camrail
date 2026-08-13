from app.database import engine
from sqlalchemy import text

with engine.connect() as con:
    con.execute(text("UPDATE alembic_version SET version_num = '522cec1eedc7';"))
    con.execute(text("DROP TABLE IF EXISTS conversation_messages;"))
    con.execute(text("DROP TABLE IF EXISTS conversations;"))
    con.commit()
    print("DB reset to 522cec1eedc7")
