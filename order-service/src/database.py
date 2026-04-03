import os
from sqlalchemy import create_engine, Column, String, JSON, Enum, DateTime, Boolean, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    items = Column(JSON, nullable=False)
    status = Column(Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'), default='PENDING')
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    event_id = Column(String(36), nullable=False)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id = Column(String(36), primary_key=True)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(36), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    processed = Column(Boolean, default=False)

def get_db_url():
    host = os.getenv("MYSQL_HOST", "localhost")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "rootpassword")
    db_name = os.getenv("ORDER_DB", "order_db")
    return f"mysql+mysqlconnector://{user}:{password}@{host}/{db_name}"

engine = create_engine(get_db_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
