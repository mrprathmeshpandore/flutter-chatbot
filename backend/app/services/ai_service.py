import json
import logging
import random
import re
import time
from typing import Optional, List, Dict, Any, Tuple, Generator
import httpx
from sqlalchemy.orm import Session
from app.config import settings
from app.models import PDFDocument, PDFPage
from app.services.pdf_service import search_relevant_pages, search_relevant_chunks

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Base exception for Gemini AI service errors."""
    def __init__(
        self,
        message: str = "The AI service encountered an error.",
        status_code: int = 503,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.original_error = original_error


class AIServiceUnavailableError(AIServiceError):
    """Raised when Gemini AI is temporarily unavailable (e.g. 503 high demand, 429 rate limit)."""
    def __init__(
        self,
        message: str = "The AI service is temporarily unavailable due to high demand. Please try again later.",
        status_code: int = 503,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, status_code=status_code, original_error=original_error)


class AIServiceConfigurationError(AIServiceError):
    """Raised when Gemini AI is misconfigured (missing API key, unsupported model 404, auth 401/403)."""
    def __init__(
        self,
        message: str = "The AI service configuration is invalid. Please check your settings.",
        status_code: int = 502,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message, status_code=status_code, original_error=original_error)


def is_transient_gemini_error(exc: Exception) -> Tuple[bool, int, str]:
    """
    Determines whether a Gemini API error is transient and retryable (e.g. 429, 500, 502, 503, 504).
    Returns (is_transient, status_code, reason).
    """
    # 1. Check if the exception has an integer HTTP code (e.g. google.genai.errors.APIError)
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        if code in (429, 500, 502, 503, 504):
            return True, code, f"HTTP_{code}"
        if code in (400, 401, 403, 404):
            return False, code, f"HTTP_{code}"

    # 2. Check for network / timeout exceptions
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return True, 504, "NETWORK_TIMEOUT"
    if isinstance(exc, (httpx.NetworkError, ConnectionError)):
        return True, 503, "NETWORK_CONNECTION_ERROR"

    # 3. Check status attribute if present
    status_attr = str(getattr(exc, "status", "")).upper()
    if status_attr in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED"):
        code_map = {
            "UNAVAILABLE": 503,
            "RESOURCE_EXHAUSTED": 429,
            "INTERNAL": 500,
            "DEADLINE_EXCEEDED": 504,
        }
        return True, code_map.get(status_attr, 503), status_attr

    # 4. Check string contents
    exc_str = str(exc).upper()
    if "TIMEOUT" in exc_str or "TIMED OUT" in exc_str or "DEADLINE" in exc_str:
        return True, 504, "REQUEST_TIMEOUT"
    if "503" in exc_str or "UNAVAILABLE" in exc_str or "HIGH DEMAND" in exc_str:
        return True, 503, "503_UNAVAILABLE"
    if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str or "TOO MANY REQUESTS" in exc_str or "QUOTA" in exc_str:
        return True, 429, "429_RATE_LIMIT"
    if "500" in exc_str or "INTERNAL SERVER ERROR" in exc_str or "INTERNAL" in exc_str:
        return True, 500, "500_INTERNAL"
    if "502" in exc_str or "BAD GATEWAY" in exc_str:
        return True, 502, "502_BAD_GATEWAY"
    if "504" in exc_str or "GATEWAY TIMEOUT" in exc_str:
        return True, 504, "504_GATEWAY_TIMEOUT"
    if "404" in exc_str or "NOT_FOUND" in exc_str:
        return False, 404, "404_NOT_FOUND"
    if "401" in exc_str or "UNAUTHENTICATED" in exc_str or "INVALID API KEY" in exc_str:
        return False, 401, "401_UNAUTHENTICATED"
    if "403" in exc_str or "PERMISSION_DENIED" in exc_str:
        return False, 403, "403_FORBIDDEN"
    if "400" in exc_str or "INVALID_ARGUMENT" in exc_str:
        return False, 400, "400_BAD_REQUEST"

    return False, 500, "UNKNOWN_ERROR"


def sanitize_gemini_error(msg: str) -> str:
    """Removes API keys and sensitive tokens from error and log messages."""
    if not msg:
        return ""
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY in msg:
        msg = msg.replace(settings.GEMINI_API_KEY, "[REDACTED_API_KEY]")
    msg = re.sub(r"(key=)[A-Za-z0-9_\-\.]{10,}", r"\1[REDACTED]", msg)
    msg = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", r"\1[REDACTED]", msg)
    return msg


class AIService:
    """
    AI Teacher service powered by Google Gemini API.
    Handles grounded Q&A with PDF context, learning path generation,
    topic explanations, and quiz question authoring.
    """

    @classmethod
    def get_client(cls):
        """Initializes and returns the Gemini Client with a finite HTTP timeout if API key is configured."""
        if not settings.GEMINI_API_KEY:
            return None
        try:
            from google import genai
            from google.genai import types
            timeout_ms = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 10.0) * 1000)
            http_options = types.HttpOptions(timeout=timeout_ms)
            return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=http_options)
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini Client: {sanitize_gemini_error(str(e))}")
            return None

    @classmethod
    def _raise_mapped_error(cls, status_code: int, reason: str, original_error: Optional[Exception] = None):
        """Maps HTTP/API status codes to clean, safe, user-facing AIService errors."""
        if status_code == 504 or "TIMEOUT" in reason.upper():
            raise AIServiceUnavailableError(
                message="The AI service request timed out while generating content. Please try again later.",
                status_code=504,
                original_error=original_error,
            )
        elif status_code == 503:
            raise AIServiceUnavailableError(
                message="The AI service is temporarily unavailable due to high demand. Please try again later.",
                status_code=503,
                original_error=original_error,
            )
        elif status_code == 429:
            raise AIServiceUnavailableError(
                message="The AI service rate limit has been exceeded. Please try again in a few moments.",
                status_code=429,
                original_error=original_error,
            )
        elif status_code == 404:
            raise AIServiceConfigurationError(
                message=f"The configured AI model '{settings.GEMINI_MODEL}' is not available or supported. Please check GEMINI_MODEL in .env.",
                status_code=502,
                original_error=original_error,
            )
        elif status_code in (401, 403):
            raise AIServiceConfigurationError(
                message="Authentication with the AI service failed. Please check your GEMINI_API_KEY in .env.",
                status_code=502,
                original_error=original_error,
            )
        else:
            raise AIServiceUnavailableError(
                message="The AI service is currently unavailable. Please try again later.",
                status_code=503 if status_code >= 500 else 502,
                original_error=original_error,
            )

    @classmethod
    def generate_text(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """
        Sends a generation request to the Gemini API with a finite timeout, bounded retry,
        exponential backoff, and jitter for transient 429/500/503/504 errors.
        """
        if not settings.GEMINI_API_KEY:
            raise AIServiceConfigurationError(
                message="Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env.",
                status_code=503,
            )

        client = cls.get_client()
        if not client:
            raise AIServiceConfigurationError(
                message="Failed to initialize Gemini AI client. Please check your configuration.",
                status_code=503,
            )

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System Instructions:\n{system_instruction}\n\nUser Request:\n{prompt}"

        effective_timeout = timeout_seconds if timeout_seconds is not None else getattr(settings, "GEMINI_TIMEOUT_SECONDS", 10.0)
        timeout_ms = int(max(0.1, effective_timeout) * 1000)

        max_retries = max(0, getattr(settings, "GEMINI_MAX_RETRIES", 2))
        initial_delay = max(0.001, getattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 1.0))
        max_delay = max(initial_delay, getattr(settings, "GEMINI_MAX_RETRY_DELAY", 4.0))
        backoff_factor = 2.0

        last_error: Optional[Exception] = None
        last_status_code = 503
        last_reason = "UNAVAILABLE"

        for attempt in range(max_retries + 1):
            try:
                try:
                    from google.genai import types
                    config = types.GenerateContentConfig(
                        http_options=types.HttpOptions(timeout=timeout_ms)
                    )
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=full_prompt,
                        config=config,
                    )
                except (TypeError, AttributeError):
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=full_prompt,
                    )
                return response.text or ""
            except Exception as exc:
                last_error = exc
                is_transient, status_code, reason = is_transient_gemini_error(exc)
                last_status_code = status_code
                last_reason = reason
                safe_err = sanitize_gemini_error(str(exc))

                if not is_transient:
                    logger.error(
                        f"Non-transient Gemini API error ({reason}, code={status_code}): {safe_err}"
                    )
                    cls._raise_mapped_error(status_code, reason, exc)

                if attempt < max_retries:
                    base_delay = min(max_delay, initial_delay * (backoff_factor ** attempt))
                    jitter = random.uniform(0.0, base_delay * 0.5)
                    delay = (base_delay * 0.5) + jitter
                    logger.warning(
                        f"Gemini API transient error ({reason}, code={status_code}): {safe_err}. "
                        f"Retrying attempt {attempt + 1}/{max_retries} in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Gemini API retries exhausted ({max_retries} retries). "
                        f"Final error ({reason}, code={status_code}): {safe_err}"
                    )

        cls._raise_mapped_error(last_status_code, last_reason, last_error)

    @classmethod
    def generate_text_stream(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Generator[str, None, None]:
        """
        Sends a streaming generation request to the Gemini API with native streaming,
        yielding incremental text chunks with minimal Time To First Token (TTFT).
        """
        if not settings.GEMINI_API_KEY:
            raise AIServiceConfigurationError(
                message="Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env.",
                status_code=503,
            )

        client = cls.get_client()
        if not client:
            raise AIServiceConfigurationError(
                message="Failed to initialize Gemini AI client. Please check your configuration.",
                status_code=503,
            )

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System Instructions:\n{system_instruction}\n\nUser Request:\n{prompt}"

        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "GEMINI_TIMEOUT_SECONDS", 12.0)
        )
        timeout_ms = int(max(0.1, effective_timeout) * 1000)

        response_stream = None
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=timeout_ms)
            )
            response_stream = client.models.generate_content_stream(
                model=settings.GEMINI_MODEL,
                contents=full_prompt,
                config=config,
            )
        except (TypeError, AttributeError):
            try:
                response_stream = client.models.generate_content_stream(
                    model=settings.GEMINI_MODEL,
                    contents=full_prompt,
                )
            except Exception as exc:
                is_transient, status_code, reason = is_transient_gemini_error(exc)
                safe_err = sanitize_gemini_error(str(exc))
                logger.error(
                    f"Gemini API streaming error ({reason}, code={status_code}): {safe_err}"
                )
                cls._raise_mapped_error(status_code, reason, exc)
        except Exception as exc:
            is_transient, status_code, reason = is_transient_gemini_error(exc)
            safe_err = sanitize_gemini_error(str(exc))
            logger.error(
                f"Gemini API streaming error ({reason}, code={status_code}): {safe_err}"
            )
            cls._raise_mapped_error(status_code, reason, exc)

        if response_stream is not None:
            try:
                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
            except Exception as exc:
                is_transient, status_code, reason = is_transient_gemini_error(exc)
                safe_err = sanitize_gemini_error(str(exc))
                logger.error(
                    f"Gemini API streaming chunk iteration error ({reason}, code={status_code}): {safe_err}"
                )
                cls._raise_mapped_error(status_code, reason, exc)

    @classmethod
    def _build_ai_teacher_prompt(
        cls,
        question: str,
        pdf: Optional[PDFDocument],
        db: Session,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
    ) -> Tuple[str, str, List[int], bool]:
        """
        Builds the grounded RAG context, strict document-only instructions,
        personalized student name context, and full prompt for AI Teacher.
        Returns (full_prompt, system_instruction, source_pages, has_relevant_content).
        """
        source_pages: List[int] = []
        context_str = ""
        has_relevant_content = True

        # Retrieve relevant PDF chunks using semantic thresholded search
        if pdf:
            relevant_chunks, max_score = search_relevant_chunks(
                pdf_id=pdf.id,
                query=question,
                db=db,
            )

            if relevant_chunks:
                source_pages = sorted(list(set(c["page_number"] for c in relevant_chunks)))
                context_blocks = []
                for chunk in relevant_chunks:
                    page_number = chunk["page_number"]
                    context_blocks.append(
                        f"--- [Page {page_number}] ---\n"
                        f"{chunk['text']}\n"
                    )
                context_str = "\n".join(context_blocks)
            else:
                has_relevant_content = False
                context_str = (
                    "NO_RELEVANT_CONTENT_FOUND_IN_UPLOADED_PDF. "
                    "The uploaded document does not contain information to answer this question."
                )

        clean_name = user_name.strip() if user_name and user_name.strip() else None
        name_instruction = ""
        if clean_name:
            name_instruction = (
                f"STUDENT PROFILE:\n"
                f"- The student's registered name is '{clean_name}'.\n"
                f"- Address the student naturally by their name where appropriate (e.g., in greetings or encouragement, such as 'Sure {clean_name}, let's look at this concept').\n"
                f"- Do NOT repeat the student's name unnaturally in every single sentence.\n"
                f"- Personalization must NEVER override document grounding, factual accuracy, or safety guidelines.\n\n"
            )

        if pdf:
            system_instruction = (
                f"You are MindVault AI, an academic assistant analyzing the user's uploaded document: '{pdf.title}'.\n\n"
                f"{name_instruction}"
                "CRITICAL GROUNDING RULES:\n"
                "1. Answer the student's question STRICTLY and EXCLUSIVELY based on the DOCUMENT CONTEXT provided below.\n"
                "2. Cite facts from the document using exact bracketed page citations like [Page 1] or [Page 2].\n"
                "3. NEVER use general knowledge, external assumptions, or outside training data to answer or embellish.\n"
                "4. If the provided DOCUMENT CONTEXT does not contain enough information to fully answer the question, state EXACTLY:\n"
                "'I could not find this information in your uploaded document.'\n"
                "Do NOT attempt to guess, hypothesize, or provide a general educational explanation.\n"
                "5. Maintain clean markdown formatting with headings and bullet points where helpful."
            )
        else:
            system_instruction = (
                "You are MindVault AI, an inspiring, empathetic, and expert Personal AI Teacher. "
                "Your mission is to help students understand concepts with maximum clarity, intelligence, and structure.\n\n"
                f"{name_instruction}"
                "ADAPTIVE PROGRESSIVE ANSWER STRUCTURE:\n"
                "- Simple questions: Give a clear, direct, and complete answer in 1-2 short paragraphs.\n"
                "- Step-by-step or process questions: Use clean numbered steps (1., 2., 3.) with bold action phrases.\n"
                "- Technical or complex concepts: Start with a clear 1-2 sentence core definition. "
                "Follow with '### How It Works' or '### Key Concepts' using concise bullet points. "
                "Conclude with '### Why It Matters' or a real-world takeaway.\n"
                "- Coding questions: Provide a brief explanation followed by clean, formatted code blocks with syntax highlighting and helpful comments.\n"
                "- Readability rules: Break text into short, digestible paragraphs (2-3 sentences max). Use bold text for key terms. Avoid monolithic walls of text."
            )

        prompt_parts = []
        if context_str:
            prompt_parts.append(
                f"DOCUMENT CONTEXT (PDF: '{pdf.title}'):\n"
                f"{context_str}\n"
            )

        if history:
            prompt_parts.append("CONVERSATION HISTORY:")
            for msg in history[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.title()}: {content}")
            prompt_parts.append("")

        prompt_parts.append(f"STUDENT QUESTION: {question}")
        full_prompt = "\n".join(prompt_parts)

        return full_prompt, system_instruction, source_pages, has_relevant_content

    @classmethod
    def ask_ai_teacher(
        cls,
        question: str,
        pdf: Optional[PDFDocument],
        db: Session,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming personal AI teacher response strictly grounded in document context.
        """
        full_prompt, system_instruction, source_pages, has_relevant_content = (
            cls._build_ai_teacher_prompt(
                question=question,
                pdf=pdf,
                db=db,
                history=history,
                user_name=user_name,
            )
        )

        # Fast exit if PDF is attached but query contains zero relevant content
        if pdf and not has_relevant_content:
            logger.info(
                "RAG Grounding Guard | pdf_id=%s, question='%s' -> No relevant content found",
                pdf.id,
                question[:50],
            )
            return {
                "answer": "I could not find this information in your uploaded document.",
                "source_pages": [],
                "used_pdf": True,
                "pdf_id": pdf.id,
            }

        # Generate AI answer
        raw_answer = cls.generate_text(
            full_prompt,
            system_instruction=system_instruction,
        )

        # Keep only valid page citations
        cited_pages = []
        for match in re.findall(
            r"\[Page\s*(\d+)\]",
            raw_answer,
            re.IGNORECASE,
        ):
            page_num = int(match)
            if page_num in source_pages and page_num not in cited_pages:
                cited_pages.append(page_num)

        # If answer states information was not found, citations must be empty
        if "could not find" in raw_answer.lower() and "document" in raw_answer.lower():
            cited_pages = []

        return {
            "answer": raw_answer,
            "source_pages": sorted(cited_pages) if pdf else [],
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
        }

    @classmethod
    def ask_ai_teacher_stream(
        cls,
        question: str,
        pdf: Optional[PDFDocument],
        db: Session,
        history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming personal AI teacher generator yielding initial metadata,
        real-time tokens, and final citation verification.
        """
        full_prompt, system_instruction, source_pages, has_relevant_content = (
            cls._build_ai_teacher_prompt(
                question=question,
                pdf=pdf,
                db=db,
                history=history,
                user_name=user_name,
            )
        )

        # Fast exit if PDF is attached but query contains zero relevant content
        if pdf and not has_relevant_content:
            logger.info(
                "RAG Stream Grounding Guard | pdf_id=%s, question='%s' -> No relevant content found",
                pdf.id,
                question[:50],
            )
            yield {
                "type": "metadata",
                "used_pdf": True,
                "pdf_id": pdf.id,
                "source_pages": [],
            }
            yield {
                "type": "token",
                "text": "I could not find this information in your uploaded document.",
            }
            yield {
                "type": "done",
                "source_pages": [],
                "used_pdf": True,
                "pdf_id": pdf.id,
                "full_answer": "I could not find this information in your uploaded document.",
            }
            return

        # 1. Immediately yield metadata so client can prepare UI
        yield {
            "type": "metadata",
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
            "source_pages": source_pages,
        }

        # 2. Stream incremental text tokens with zero artificial delay
        full_answer = ""
        for chunk in cls.generate_text_stream(
            full_prompt,
            system_instruction=system_instruction,
        ):
            full_answer += chunk
            yield {
                "type": "token",
                "text": chunk,
            }

        # 3. Compute final valid citations
        cited_pages = []
        for match in re.findall(
            r"\[Page\s*(\d+)\]",
            full_answer,
            re.IGNORECASE,
        ):
            page_num = int(match)
            if page_num in source_pages and page_num not in cited_pages:
                cited_pages.append(page_num)

        if "could not find" in full_answer.lower() and "document" in full_answer.lower():
            cited_pages = []

        # 4. Yield completion event
        yield {
            "type": "done",
            "source_pages": sorted(cited_pages) if pdf else [],
            "used_pdf": bool(pdf),
            "pdf_id": pdf.id if pdf else None,
            "full_answer": full_answer,
        }

    @classmethod
    def generate_learning_path(cls, pdf: PDFDocument, db: Session) -> Dict[str, Any]:
        """
        Analyzes the PDF document content and generates a structured learning roadmap.
        """
        # Collect sample text from first 8 pages
        pages = db.query(PDFPage).filter(PDFPage.pdf_id == pdf.id).order_by(PDFPage.page_number).limit(8).all()
        extracted_content = "\n\n".join([f"Page {p.page_number}: {p.text_content[:800]}" for p in pages])

        prompt = f"""
You are an expert curriculum designer. Analyze this textbook/document excerpt and create a structured Learning Path for a student.

DOCUMENT TITLE: {pdf.title}
DOCUMENT EXCERPT:
{extracted_content}

Return ONLY a valid JSON object with the following exact structure (no other markdown or text outside JSON):
{{
  "title": "{pdf.title} - Complete Learning Roadmap",
  "overview": "Comprehensive roadmap designed to take you from fundamentals to mastery.",
  "estimated_hours": 5.0,
  "topics": [
    {{
      "title": "Topic Name",
      "description": "Brief description of the concept and why it matters.",
      "difficulty": "beginner",
      "estimated_minutes": 45,
      "key_points": ["Key concept 1", "Key concept 2"]
    }}
  ]
}}
Provide between 3 and 7 coherent topics covering the material sequentially.
"""
        response_text = cls.generate_text(prompt)
        
        # Parse JSON
        parsed_data = cls._extract_json(response_text)
        if (
            parsed_data
            and isinstance(parsed_data, dict)
            and "topics" in parsed_data
            and isinstance(parsed_data["topics"], list)
            and len(parsed_data["topics"]) > 0
        ):
            return parsed_data

        logger.error(
            f"Failed to extract valid learning path JSON from Gemini response for PDF '{pdf.title}'"
        )
        raise AIServiceError(
            message="Unable to generate a structured learning path from the document content. Please try again.",
            status_code=502,
        )

    @classmethod
    def explain_topic(cls, pdf: PDFDocument, topic: str, depth: str, db: Session) -> str:
        """
        Explains a specific topic from the PDF at the chosen depth (beginner, intermediate, advanced).
        """
        relevant_pages = search_relevant_pages(pdf.id, topic, db, max_pages=3)
        context = "\n".join([f"[Page {p['page_number']}]: {p['text']}" for p in relevant_pages])

        prompt = f"""
You are an expert tutor. Explain the following topic from the student's study material '{pdf.title}'.

TOPIC: {topic}
TARGET DEPTH: {depth} (beginner = intuitive analogies & simple terms; intermediate = standard academic rigor; advanced = in-depth nuances & edge cases)

SOURCE CONTEXT:
{context}

Provide a well-structured explanation including:
1. Quick Summary / Intuition
2. Core Breakdown (with bullet points)
3. Real-world Example or Analogy
4. Source references (cite [Page X] when referencing context)
"""
        return cls.generate_text(prompt)

    @classmethod
    def _extract_json(cls, text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses JSON from response text even if wrapped in markdown codeblocks."""
        # Try finding json in ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try parsing the whole text or between first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except json.JSONDecodeError:
                pass

        return None
