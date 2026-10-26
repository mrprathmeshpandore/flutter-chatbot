# MindVault AI — Backend API (Personal AI Teacher)

FastAPI-powered backend for **MindVault AI — Personal AI Teacher**, providing document-grounded AI tutoring, automated quiz generation, personalized learning paths, and progress tracking for the Flutter application.

---

## 📁 Project Architecture & Folder Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── config.py           # Pydantic Settings & environment variable management
│   ├── database.py         # SQLAlchemy engine, session maker, base model
│   ├── main.py             # FastAPI entrypoint, CORS, global error handling, routers
│   ├── models.py           # SQLAlchemy database models (User, PDFDocument, Quiz, etc.)
│   ├── schemas.py          # Pydantic models for validation and serialization
│   ├── routers/            # API endpoints grouped by domain
│   │   ├── __init__.py
│   │   ├── auth.py         # POST /auth/register, POST /auth/login, GET /auth/me
│   │   ├── pdf.py          # POST /pdf/upload, GET /pdf/, GET /pdf/{id}, DELETE /pdf/{id}
│   │   ├── learning_path.py# GET /pdf/{id}/learning-path, POST /pdf/{id}/explain
│   │   ├── ai.py           # POST /ai/ask (PDF-grounded citations or general tutoring)
│   │   ├── quiz.py         # POST /quiz/generate, POST /quiz/submit, GET /quiz/{id}/results
│   │   └── progress.py     # GET /progress/summary, GET /progress/subjects
│   └── services/           # Business logic layer
│       ├── __init__.py
│       ├── auth_service.py # Password hashing (bcrypt) & JWT issuance/decoding
│       ├── pdf_service.py  # File validation, size limits, PyPDF extraction & chunking
│       ├── ai_service.py   # Google Gemini API integration with citation grounding & fallback
│       └── quiz_service.py # Dynamic quiz generation, answer scoring & mastery calculation
├── tests/                  # Pytest test suite (33 comprehensive tests)
│   ├── __init__.py
│   ├── conftest.py         # Test fixtures, mock Gemini client, test DB setup
│   ├── test_auth.py
│   ├── test_pdf.py
│   ├── test_learning_path.py
│   ├── test_ai.py
│   ├── test_quiz.py
│   └── test_progress.py
├── uploads/                # Directory for securely stored user PDF files
├── .env.example            # Template for environment configuration
├── .gitignore              # Ignores venv, .env, DB files, uploads, and caches
├── init_db.py              # Command-line database table initialization script
├── requirements.txt        # Python package dependencies
└── README.md               # Backend documentation
```

---

## ⚙️ Prerequisites

- **Python**: Version 3.10 to 3.14
- **PostgreSQL**: Version 14+ (or SQLite for lightweight local testing)
- **Google Gemini API Key**: Free key from [Google AI Studio](https://aistudio.google.com/)

---

## 🔑 Environment Variables Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Key variables configured in `.env`:
| Variable | Description | Example / Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `postgresql+psycopg2://postgres:postgres@localhost:5432/mindvault_db` |
| `SECRET_KEY` | Secret key for JWT signing | `random_32_byte_string` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiration duration in minutes | `10080` (7 days) |
| `GEMINI_API_KEY` | API Key for Google Gemini | `AIzaSy...` |
| `GEMINI_MODEL` | Gemini model variant | `gemini-1.5-flash` |
| `MAX_FILE_SIZE_MB` | Maximum allowed PDF size in megabytes | `15` |
| `CORS_ORIGINS` | Allowed CORS origins for Flutter app | `*` (or `http://localhost:3000`) |

---

## 🗄️ PostgreSQL Database Setup

### 1. Create PostgreSQL Database
Open PostgreSQL shell (`psql`) or pgAdmin:
```sql
CREATE DATABASE mindvault_db;
CREATE USER postgres WITH ENCRYPTED PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE mindvault_db TO postgres;
```

*(Optional SQLite fallback)*:
If you do not have PostgreSQL installed, you can simply use SQLite by setting:
```ini
DATABASE_URL=sqlite:///./mindvault.db
```

### 2. Initialize Database Tables
Run the database schema setup script:
```bash
python init_db.py
```
This automatically inspects all SQLAlchemy models and generates all tables (`users`, `pdf_documents`, `pdf_pages`, `learning_paths`, `quizzes`, `quiz_questions`, `quiz_attempts`, `user_answers`, `study_progress`).

---

## 🚀 Installation & Running the Server

### 1. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the FastAPI Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Server will be accessible at: `http://localhost:8000`

---

## 🧪 Testing with Pytest

To run the automated test suite (33 tests covering auth, PDF uploads, Gemini mocking, quiz scoring, and progress):
```bash
pytest -v
```

All external calls to the Gemini API are cleanly mocked in tests to guarantee fast, deterministic, offline execution.

---

## 📖 Interactive Swagger API Documentation

Once the server is running, navigate to:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### How to test in Swagger:
1. Open [http://localhost:8000/docs](http://localhost:8000/docs).
2. Go to **`POST /auth/register`** -> click **Try it out** -> enter email and password -> execute.
3. Copy the returned `access_token`.
4. Click the green **Authorize** button at the top right of the Swagger page, type `Bearer <your_token>`, and click Authorize.
5. All protected endpoints (`/pdf/upload`, `/ai/ask`, `/quiz/generate`, `/progress/summary`, etc.) are now authorized and ready to test!

---

## 📋 Features Status Summary

| Feature / Endpoint | Implementation Status | Notes |
|---|---|---|
| **JWT Authentication** (`/auth/register`, `/auth/login`, `/auth/me`) | ✅ Fully Implemented | Bcrypt hashing, JWT issuance & decoding, Bearer token security |
| **PDF Library** (`/pdf/upload`, `/pdf/`, `/pdf/{id}`, `/pdf/{id}`) | ✅ Fully Implemented | Magic byte validation, size limit checks, text extraction & page-wise indexing |
| **Learning Path** (`/pdf/{id}/learning-path`, `/pdf/{id}/explain`) | ✅ Fully Implemented | Topic extraction, milestone roadmap, document-grounded deep dive explanations |
| **AI Teacher** (`/ai/ask`) | ✅ Fully Implemented | Document-grounded answers with citations `[Page X]`, zero-hallucination citations fallback, general mode |
| **Quiz Generator & Scorer** (`/quiz/generate`, `/quiz/submit`, `/quiz/{id}/results`) | ✅ Fully Implemented | Dynamic MCQ generation from topics or uploaded PDFs, automated scoring & mastery calculation |
| **Progress Tracking** (`/progress/summary`, `/progress/subjects`) | ✅ Fully Implemented | Aggregated quiz scores, time spent, mastery percentage, subject-wise analytics |
| **Database Migrations** | ⚠️ Schema initialized via `init_db.py` | Alembic can be added in future iterations if dynamic migration versioning is required |
