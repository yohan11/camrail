from app.database import engine
from sqlalchemy import text
with engine.connect() as con:
    rs = con.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'documents';"))
    for row in rs:
        print(f'{row[0]}: {row[1]}')
