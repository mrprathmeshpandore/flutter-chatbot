from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field


# ==========================================
# Authentication & User Schemas
# ==========================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserOut] = None


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None


# ==========================================
# PDF Library Schemas
# ==========================================

class PDFPageOut(BaseModel):
    id: int
    page_number: int
    text_content: str

    class Config:
        from_attributes = True


class PDFDocumentOut(BaseModel):
    id: int
    title: str
    filename: str
    file_size: int
    page_count: int
    uploaded_at: datetime
    owner_id: int

    class Config:
        from_attributes = True


class PDFDocumentDetail(PDFDocumentOut):
    pages: List[PDFPageOut] = []
    has_learning_path: bool = False


# ==========================================
# Learning Path Schemas
# ==========================================

class LearningTopic(BaseModel):
    title: str
    description: str
    difficulty: str = "beginner"
    estimated_minutes: int = 30
    key_points: List[str] = []


class LearningPathOut(BaseModel):
    id: int
    pdf_id: int
    title: str
    overview: Optional[str] = None
    estimated_hours: float
    topics: List[LearningTopic]
    created_at: datetime

    class Config:
        from_attributes = True


class ExplainTopicRequest(BaseModel):
    topic: str = Field(..., min_length=2, description="The topic from the PDF to explain")
    depth: Optional[str] = Field("beginner", description="Explanation depth: beginner, intermediate, or advanced")


class ExplainTopicResponse(BaseModel):
    topic: str
    depth: str
    explanation: str
    pdf_id: int


# ==========================================
# AI Teacher Schemas
# ==========================================

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'model'/'assistant'")
    content: str


class AskAIRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Student question for the AI Teacher")
    pdf_id: Optional[int] = Field(None, description="Optional PDF ID to ground the answer in specific document content")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Optional conversation history")


class AskAIResponse(BaseModel):
    answer: str
    source_pages: List[int] = []
    used_pdf: bool = False
    pdf_id: Optional[int] = None


# ==========================================
# Quiz Schemas
# ==========================================

class GenerateQuizRequest(BaseModel):
    pdf_id: Optional[int] = Field(None, description="Optional PDF ID to generate questions from")
    topic: Optional[str] = Field(None, description="Topic or subject for quiz generation")
    num_questions: int = Field(5, ge=1, le=20, description="Number of questions (1-20)")
    difficulty: Optional[str] = Field("medium", description="Quiz difficulty: easy, medium, or hard")


class QuizQuestionOut(BaseModel):
    id: int
    question_text: str
    options: List[str]

    class Config:
        from_attributes = True


class QuizQuestionWithAnswerOut(QuizQuestionOut):
    correct_option: int
    explanation: Optional[str] = None


class QuizOut(BaseModel):
    id: int
    title: str
    topic: Optional[str] = None
    difficulty: str
    total_questions: int
    pdf_id: Optional[int] = None
    questions: List[QuizQuestionOut]
    created_at: datetime

    class Config:
        from_attributes = True


class QuizAnswerItem(BaseModel):
    question_id: int
    selected_option: int = Field(..., ge=0, le=3, description="Selected option index (0 to 3)")


class SubmitQuizRequest(BaseModel):
    quiz_id: int
    answers: List[QuizAnswerItem]


class SubmittedAnswerDetail(BaseModel):
    question_id: int
    question_text: str
    options: List[str]
    selected_option: int
    correct_option: int
    is_correct: bool
    explanation: Optional[str] = None


class QuizResultOut(BaseModel):
    submission_id: int
    quiz_id: int
    quiz_title: str
    score: float
    total_questions: int
    correct_answers: int
    percentage: float
    submitted_at: datetime
    details: List[SubmittedAnswerDetail]


class QuizHistoryItem(BaseModel):
    id: int
    quiz_id: int
    score: float
    total_questions: int
    correct_answers: int
    percentage: float
    submitted_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# Progress Schemas
# ==========================================

class ActivityLogItem(BaseModel):
    activity_type: str
    subject: Optional[str] = None
    score: Optional[float] = None
    created_at: datetime


class ProgressSummaryOut(BaseModel):
    total_pdfs: int
    total_quizzes_taken: int
    average_quiz_score: float
    learning_paths_count: int
    recent_activity: List[ActivityLogItem] = []


class SubjectProgressItem(BaseModel):
    subject: str
    pdf_id: Optional[int] = None
    quizzes_taken: int
    average_score: float
    last_activity: datetime


class SubjectsProgressOut(BaseModel):
    subjects: List[SubjectProgressItem]
