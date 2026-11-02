import os
os.environ["TESTING"] = "1"
import io
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.ai_service import AIService, ai_cache
from app.services.auth_service import create_access_token
from app.models import User
from app.config import settings

# In-memory SQLite engine for fast, isolated tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Creates tables once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def reset_ai_state_for_tests(monkeypatch):
    """Resets AI cache and fallback model between tests so unit tests are deterministic."""
    ai_cache.clear()
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODEL", None)
    yield
    ai_cache.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a transactional database session rolled back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session, monkeypatch) -> Generator[TestClient, None, None]:
    """TestClient that uses the test database session."""
    ai_cache.clear()
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.routers.pdf.generate_pdf_quiz_task", lambda pdf_id, user_id: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    ai_cache.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Creates a default test user."""
    from app.services.auth_service import get_password_hash
    user = User(
        email="student@mindvault.ai",
        full_name="Alex Student",
        hashed_password=get_password_hash("password123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Returns Bearer authorization headers for the primary test user."""
    token = create_access_token(data={"sub": test_user.email, "user_id": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user(db_session: Session) -> User:
    """Creates a second user to test access control and ownership restrictions."""
    from app.services.auth_service import get_password_hash
    user = User(
        email="other@mindvault.ai",
        full_name="Other Student",
        hashed_password=get_password_hash("password123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_auth_headers(second_user: User) -> dict:
    """Returns Bearer authorization headers for the second test user."""
    token = create_access_token(data={"sub": second_user.email, "user_id": second_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """
    Returns valid PDF bytes containing text on multiple pages for testing extraction.
    """
    pdf_content = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj
4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
5 0 obj <</Length 120>> stream
BT
/F1 14 Tf
70 700 Td
(Machine Learning Fundamentals. Neural networks learn representations from data.) Tj
ET
endstream endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000229 00000 n 
0000000300 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
470
%%EOF
"""
    return pdf_content


@pytest.fixture(autouse=True)
def mock_gemini(monkeypatch, request):
    """
    Default mock for Gemini AI calls so unit tests run fast and offline.
    Specific tests can override this mock if needed.
    """
    if "disable_mock_gemini" in request.keywords:
        return

    def fake_generate_text(prompt: str, system_instruction: str = None, **kwargs) -> str:
        prompt_lower = prompt.lower()
        if "quiz" in prompt_lower or "multiple-choice" in prompt_lower or "examiner" in prompt_lower or "options" in prompt_lower:
            return '''{
              "title": "Machine Learning Core Quiz",
              "questions": [
                {
                  "question_text": "What is the primary objective of training a neural network?",
                  "options": [
                    "Minimize the loss function",
                    "Maximize memory usage",
                    "Increase latency",
                    "Disable gradient backpropagation"
                  ],
                  "correct_option": 0,
                  "explanation": "Neural networks are trained by minimizing an objective loss function via optimization algorithms."
                },
                {
                  "question_text": "Which activation function is most widely used in modern hidden layers?",
                  "options": [
                    "ReLU (Rectified Linear Unit)",
                    "Binary Step",
                    "Identity",
                    "Linear Regression"
                  ],
                  "correct_option": 0,
                  "explanation": "ReLU avoids vanishing gradients and allows efficient sparse activations."
                },
                {
                  "question_text": "What is overfitting in machine learning?",
                  "options": [
                    "Model learns training noise instead of general patterns",
                    "Model cannot fit simple training data",
                    "Model runs too slowly on hardware",
                    "Model has zero trainable parameters"
                  ],
                  "correct_option": 0,
                  "explanation": "Overfitting happens when a model memorizes noise in training data."
                },
                {
                  "question_text": "Which algorithm computes loss gradients using the calculus chain rule?",
                  "options": [
                    "Backpropagation",
                    "Binary search",
                    "Merge sort",
                    "Random walk"
                  ],
                  "correct_option": 0,
                  "explanation": "Backpropagation efficiently computes analytical gradients layer by layer."
                },
                {
                  "question_text": "Which hyperparameter scales parameter updates during gradient descent?",
                  "options": [
                    "Learning rate",
                    "Batch size",
                    "Dropout rate",
                    "Layer count"
                  ],
                  "correct_option": 0,
                  "explanation": "Learning rate controls the step magnitude along the gradient."
                }
              ]
            }'''
        elif "curriculum" in prompt_lower or "learning path" in prompt_lower or "roadmap" in prompt_lower:
            return '''{
              "title": "Machine Learning Fundamentals Roadmap",
              "overview": "A step-by-step pathway from basic linear models to deep neural networks.",
              "estimated_hours": 4.5,
              "topics": [
                {
                  "title": "Introduction to Neural Networks",
                  "description": "Perceptrons, forward propagation, and weight matrices.",
                  "difficulty": "beginner",
                  "estimated_minutes": 35,
                  "key_points": ["Weights and biases", "Activation functions", "Loss calculation"]
                },
                {
                  "title": "Backpropagation and Gradient Descent",
                  "description": "Calculating gradients using chain rule to update weights.",
                  "difficulty": "intermediate",
                  "estimated_minutes": 45,
                  "key_points": ["Chain rule", "Learning rate", "Stochastic gradient descent"]
                }
              ]
            }'''
        elif "pyramid" in prompt_lower or "egypt" in prompt_lower:
            return (
                "According to [Page 1], ancient Egyptian pyramids were constructed with remarkable architectural precision."
            )
        elif "could not find" in prompt_lower or "no_relevant_content_found" in prompt_lower:
            return "I could not find this information in your uploaded document."
        elif "explain" in prompt_lower:
            return (
                "Neural networks are mathematical function approximators inspired by biological neurons. "
                "According to [Page 1], neural networks learn representations directly from data through iterative adjustments."
            )
        else:
            return (
                "According to [Page 1], neural networks learn representations from data by adjusting internal parameters. "
                "This allows them to recognize complex patterns effectively."
            )

    def fake_generate_text_stream(prompt: str, system_instruction: str = None, timeout_seconds: float = None, **kwargs):
        full_text = fake_generate_text(prompt, system_instruction)
        chunk_size = 20
        for i in range(0, len(full_text), chunk_size):
            yield full_text[i:i + chunk_size]

    monkeypatch.setattr(AIService, "generate_text", fake_generate_text)
    monkeypatch.setattr(AIService, "generate_text_stream", fake_generate_text_stream)
