import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, TIMESTAMP, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class Inventory(Base):
    __tablename__ = "inventory"
    sku = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    last_updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    consumer_id = Column(String(100), primary_key=True)
    event_id = Column(String(36), primary_key=True)
    processed_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    __table_args__ = (PrimaryKeyConstraint('consumer_id', 'event_id'),)

# Order Table (Simplified for updates)
class OrderStatusUpdate(Base):
    __tablename__ = "orders"
    id = Column(String(36), primary_key=True)
    status = Column(String(20))
    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def get_engine(db_name_env):
    host = os.getenv("MYSQL_HOST", "localhost")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "rootpassword")
    db_name = os.getenv(db_name_env, "order_db") # Default if not provided
    url = f"mysql+mysqlconnector://{user}:{password}@{host}/{db_name}"
    return create_engine(url, pool_pre_ping=True)

inventory_engine = get_engine("INVENTORY_DB")
order_engine = get_engine("ORDER_DB")

InventorySession = sessionmaker(bind=inventory_engine)
OrderSession = sessionmaker(bind=order_engine)
