#apps/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

#represent a user session and associated conversations
class Session(Base):

    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(100), unique=True, index=True, nullable=False)
    background_choice = Column(String(50), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationship to conversations
    conversations = relationship("Conversation", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.id}, token={self.session_token}, active={self.is_active})>"

#represent a conversation turn within a session
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_transcript = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    audio_duration = Column(Float, nullable=True)  # Duration of user's speech in seconds
    processing_time = Column(Float, nullable=True)  # Time to process and respond
    
    # Relationship to session
    session = relationship("Session", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, session_id={self.session_id})>"
# Additional models can be added here as needed