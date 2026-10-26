from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Float,
    JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pdf_documents = relationship("PDFDocument", back_populates="owner", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="user", cascade="all, delete-orphan")
    quiz_submissions = relationship("QuizSubmission", back_populates="user", cascade="all, delete-orphan")
    progress_logs = relationship("ProgressLog", back_populates="user", cascade="all, delete-orphan")
    explanations = relationship("TopicExplanation", back_populates="user", cascade="all, delete-orphan")


class PDFDocument(Base):
    __tablename__ = "pdf_documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # In bytes
    page_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="pdf_documents")
    pages = relationship("PDFPage", back_populates="pdf", cascade="all, delete-orphan", order_by="PDFPage.page_number")
    learning_path = relationship("LearningPath", back_populates="pdf", uselist=False, cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="pdf")
    explanations = relationship("TopicExplanation", back_populates="pdf", cascade="all, delete-orphan")


class PDFPage(Base):
    __tablename__ = "pdf_pages"

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdf_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    page_number = Column(Integer, nullable=False)  # 1-indexed
    text_content = Column(Text, nullable=False)

    # Relationships
    pdf = relationship("PDFDocument", back_populates="pages")


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdf_documents.id", ondelete="CASCADE"), index=True, nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    overview = Column(Text, nullable=True)
    estimated_hours = Column(Float, default=0.0)
    topics = Column(JSON, nullable=False, default=list)  # List of dicts: {title, description, difficulty, estimated_minutes, key_points}
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pdf = relationship("PDFDocument", back_populates="learning_path")


class TopicExplanation(Base):
    __tablename__ = "topic_explanations"

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdf_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    topic = Column(String(255), nullable=False)
    depth = Column(String(50), default="beginner")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pdf = relationship("PDFDocument", back_populates="explanations")
    user = relationship("User", back_populates="explanations")


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    pdf_id = Column(Integer, ForeignKey("pdf_documents.id", ondelete="SET NULL"), index=True, nullable=True)
    title = Column(String(255), nullable=False)
    topic = Column(String(255), nullable=True)
    difficulty = Column(String(50), default="medium")
    total_questions = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="quizzes")
    pdf = relationship("PDFDocument", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.id")
    submissions = relationship("QuizSubmission", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # List of 4 strings: ["Option A", "Option B", ...]
    correct_option = Column(Integer, nullable=False)  # Index: 0, 1, 2, or 3
    explanation = Column(Text, nullable=True)

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")


class QuizSubmission(Base):
    __tablename__ = "quiz_submissions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    score = Column(Float, nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    submitted_answers = Column(JSON, nullable=False)  # List of dicts: {question_id, selected_option, is_correct}
    submitted_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    quiz = relationship("Quiz", back_populates="submissions")
    user = relationship("User", back_populates="quiz_submissions")


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    activity_type = Column(String(50), nullable=False)  # e.g., 'quiz_completed', 'pdf_uploaded', 'learning_path_generated'
    subject = Column(String(255), nullable=True)
    score = Column(Float, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="progress_logs")
