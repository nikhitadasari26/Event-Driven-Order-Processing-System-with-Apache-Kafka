import os
from sqlalchemy import create_engine, Column, String, TIMESTAMP, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    consumer_id = Column(String(100), primary_key=True)
    event_id = Column(String(36), primary_key=True)
    processed_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    __table_args__ = (PrimaryKeyConstraint('consumer_id', 'event_id'),)

def get_engine():
    host = os.getenv("MYSQL_HOST", "localhost")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "rootpassword")
    db_name = os.getenv("NOTIFICATION_DB", "notification_db")
    url = f"mysql+mysqlconnector://{user}:{password}@{host}/{db_name}"
    return create_engine(url, pool_pre_ping=True)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)
