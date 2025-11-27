from datetime import datetime
from sqlalchemy import Column, Integer, Text, String, ForeignKey, TIMESTAMP, JSON, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Discipline(Base):
    __tablename__ = "disciplines"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    questions = relationship("Question", back_populates="discipline", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False)
    code = Column(String, nullable=True)
    prompt_text = Column(Text, nullable=False)
    ideal_text = Column(Text, nullable=True)
    required_keywords = Column(Text, nullable=True)  # CSV or JSON string
    metadata = Column(JSON, default={})
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    discipline = relationship("Discipline", back_populates="questions")

class ChatSetting(Base):
    __tablename__ = "chat_settings"
    chat_id = Column(Integer, primary_key=True, index=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    chat_id = Column(Integer, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    audio_path = Column(Text, nullable=True)
    transcript_raw = Column(Text, nullable=True)
    transcript_norm = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    details = Column(JSON, default={})
    created_at = Column(TIMESTAMP, default=datetime.utcnow)