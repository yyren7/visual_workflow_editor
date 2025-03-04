from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    """
    Represents a user in the system.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    flows = relationship("Flow", back_populates="owner")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Flow(Base):
    """
    Represents a flow (diagram) in the system.
    """
    __tablename__ = "flows"

    id = Column(Integer, primary_key=True, index=True)
    flow_data = Column(JSON, nullable=False, default={})  # Stores the flow data as a JSON object
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="flows")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    name = Column(String, nullable=False, default="Untitled Flow")  # Added flow name

    def __repr__(self):
        return f"<Flow(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"
