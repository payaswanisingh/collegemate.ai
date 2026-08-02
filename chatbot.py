# chatbot.py

"""
High-level wrapper that loads the trained PyTorch model,
TF-IDF vectorizer and label encoder, and provides prediction.
"""

import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import torch.nn.functional as F
from docx import Document as DocxDocument
from dotenv import load_dotenv
try:
    from google import generativeai as genai
except ImportError:
    try:
        import google.generativeai as genai
    except ImportError as _genai_import_error:
        genai = None
        logging.getLogger(__name__).warning(
            "Gemini SDK ('google-generativeai') could not be imported: %s. "
            "Gemini features will be unavailable until it is installed/fixed.",
            _genai_import_error,
        )

# google-api-core ships as a dependency of google-generativeai, so this
# should always be importable whenever `genai` itself is — but it's guarded
# anyway so a partially-broken install degrades to string-matching instead
# of crashing at import time (see _classify_gemini_exception below).
try:
    from google.api_core.exceptions import (
        GoogleAPICallError,
        InvalidArgument,
        NotFound,
        PermissionDenied,
        ResourceExhausted,
        Unauthenticated,
    )
except ImportError:
    GoogleAPICallError = None
    InvalidArgument = None
    NotFound = None
    PermissionDenied = None
    ResourceExhausted = None
    Unauthenticated = None

from pypdf import PdfReader

from services.semantic_search import search_semantic
from utils import (
    load_vectorizer,
    load_label_encoder,
    load_model,
    preprocess_text,
    get_device,
    MODEL_PATH,
    load_dataset,
)

from model import ChatbotModel

logger = logging.getLogger(__name__)

load_dotenv()
import os

print("API KEY:", os.getenv("GEMINI_API_KEY"))
print("MODEL:", os.getenv("GEMINI_MODEL"))

# gemini-2.0-flash was Google's long-standing free-tier default, but it was
# deprecated and fully shut down on June 1, 2026 (see
# https://ai.google.dev/gemini-api/docs/pricing#gemini-2.0-flash). Calling a
# shut-down model doesn't behave like ordinary throttling: Google reports it
# as a 429 RESOURCE_EXHAUSTED with a hard "limit: 0" free-tier quota, which
# looks identical to a real rate limit in the logs but can never succeed no
# matter how long you wait or how few requests you send. gemini-2.5-flash is
# the current GA, free-tier-eligible replacement recommended by Google for
# exactly this migration.
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", FALLBACK_GEMINI_MODEL)

# Models that no longer serve requests at all (shut down), or that Google
# has otherwise fully retired. If GEMINI_MODEL still points at one of these
# — e.g. an old .env that predates the June 2026 shutdown — _init_gemini
# swaps in FALLBACK_GEMINI_MODEL automatically instead of quietly failing
# on every single request with a misleading "quota exceeded" message.
# Update this table as Google retires further models; see
# https://ai.google.dev/gemini-api/docs/deprecations for the current list.
DEPRECATED_GEMINI_MODELS = {
    "gemini-2.0-flash": "shut down by Google on June 1, 2026",
    "gemini-2.0-flash-lite": "shut down by Google on June 1, 2026",
    "gemini-1.5-flash": "retired",
    "gemini-1.5-flash-8b": "retired",
    "gemini-1.5-pro": "retired",
    "gemini-pro": "retired (legacy alias)",
}

GEMINI_SYSTEM_PROMPT = (
    "You are CampusMate AI, a professional university assistant for college and university students. "
    "Your tone should be friendly, confident, polished, and easy to read.\n\n"
    "Use this style guidance for every answer:\n"
    "- Write clearly and professionally, with a natural conversational voice.\n"
    "- Keep simple answers concise and direct; expand only when the question requires more detail.\n"
    "- Use headings, bullet points, or numbered steps when they improve readability.\n"
    "- Avoid robotic wording, repeated phrases, and unnecessary filler.\n"
    "- Stay focused on the student's question and avoid reintroducing yourself.\n"
    "- If a follow-up question is asked, answer it directly and naturally using prior conversation context.\n"
    "- Do not say 'As an AI language model' or any similar self-description.\n"
    "- Do not repeat the same greeting phrases within the same session.\n\n"
    "Conversation rules:\n"
    "- Greet the user only once at the beginning of a new conversation.\n"
    "- If this is the first assistant response in this conversation, open with a warm welcome and use the student's name when available.\n"
    "- If the conversation already has prior assistant messages, do not greet again, reintroduce yourself, or use phrases like 'Hi', 'Hello', 'Greetings', 'Hi again', or 'Hello again'.\n"
    "- Continue the conversation naturally, as if the student and assistant are already in the same session.\n"
    "- Never repeat information that has already been answered unless the user asks for clarification.\n\n"
    "Knowledge and behavior:\n"
    "- Use the provided campus context and retrieved information only when it is relevant.\n"
    "- If relevant knowledge is available, incorporate it smoothly without saying 'retrieved context' or 'knowledge base'.\n"
    "- If the answer requires university-specific detail and it is not available, say so politely and clearly.\n"
    "- Stay within the scope of university, admissions, academics, fees, placements, facilities, student services, and student life.\n"
    "- If the user asks something outside those topics, reply with: \"I'm here to help with university and college-related questions. Please ask me something about admissions, academics, fees, facilities, placements, student life, or education.\"\n"
)

CONFIDENCE_THRESHOLD = 15.0
SIMILARITY_THRESHOLD = 0.8
CONTEXT_RELEVANCE_THRESHOLD = 0.8
TOP_K_CONTEXT_ROWS = 4

# Pulls a human-readable retry hint out of google-api-core's exception
# message, e.g. "...Please retry in 51.203696311s." -> 51.2. Best-effort:
# if the SDK ever changes this wording, callers just get retry_after=None
# and fall back to a generic "try again shortly" message instead of a
# specific countdown.
_RETRY_DELAY_RE = re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE)


def _classify_gemini_exception(exc: Exception) -> Dict[str, Any]:
    """Turn a raw Gemini SDK exception into a small, stable status the rest
    of the app can branch and report on, instead of a raw stack-trace
    string that's identical for "quota exceeded" and "your API key is
    wrong" and "the model name doesn't exist".

    Returns a dict with:
      - status: one of "quota_exceeded", "invalid_api_key", "invalid_model",
        "invalid_request", "content_blocked", "unavailable"
      - message: a short, student-safe description of what happened
      - retry_after: seconds until retry might succeed, if Gemini reported
        one (only meaningful for "quota_exceeded"); otherwise None
    """
    retry_match = _RETRY_DELAY_RE.search(str(exc))
    retry_after = float(retry_match.group(1)) if retry_match else None

    if ResourceExhausted is not None and isinstance(exc, ResourceExhausted):
        return {"status": "quota_exceeded", "message": "Gemini quota exceeded", "retry_after": retry_after}
    if Unauthenticated is not None and isinstance(exc, Unauthenticated):
        return {"status": "invalid_api_key", "message": "Gemini API key was rejected", "retry_after": None}
    if PermissionDenied is not None and isinstance(exc, PermissionDenied):
        return {
            "status": "invalid_api_key",
            "message": "Gemini API key does not have permission for this model",
            "retry_after": None,
        }
    if NotFound is not None and isinstance(exc, NotFound):
        return {"status": "invalid_model", "message": "Configured Gemini model was not found", "retry_after": None}
    if InvalidArgument is not None and isinstance(exc, InvalidArgument):
        return {"status": "invalid_request", "message": "Gemini rejected the request", "retry_after": None}

    # Fallback for when google.api_core wasn't importable, or the SDK ever
    # raises something outside its own typed exception hierarchy (e.g. a
    # raw grpc/network error) — string-match the same signals a human would
    # look for in the log line.
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return {"status": "quota_exceeded", "message": "Gemini quota exceeded", "retry_after": retry_after}
    if "401" in text or "UNAUTHENTICATED" in text or "API key not valid" in text:
        return {"status": "invalid_api_key", "message": "Gemini API key was rejected", "retry_after": None}
    if "403" in text or "PERMISSION_DENIED" in text:
        return {
            "status": "invalid_api_key",
            "message": "Gemini API key does not have permission for this model",
            "retry_after": None,
        }
    if "404" in text or "NOT_FOUND" in text:
        return {"status": "invalid_model", "message": "Configured Gemini model was not found", "retry_after": None}

    return {"status": "unavailable", "message": "Gemini is temporarily unavailable", "retry_after": None}


class Chatbot:

    def __init__(self):
        self.device = get_device()
        logger.info(f"Using device: {self.device}")

        self.vectorizer = load_vectorizer()
        self.label_encoder = load_label_encoder()

        input_dim = len(self.vectorizer.get_feature_names_out())
        num_classes = len(self.label_encoder.classes_)

        self.model = load_model(
            ChatbotModel,
            input_dim=input_dim,
            num_classes=num_classes,
            path=MODEL_PATH,
            device=self.device,
        )

        self.df = load_dataset().copy()
        self.df["processed_question"] = self.df["question"].fillna("").apply(preprocess_text)
        self.dataset_vectors = self.vectorizer.transform(self.df["processed_question"]).toarray()
        self.known_question_lookup = {
            processed: idx for idx, processed in enumerate(self.df["processed_question"].tolist())
        }

        self.gemini_api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.gemini_model_name = (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
        self.gemini_model = None
        self.gemini_ready = False
        self.gemini_error = None
        self._init_gemini()

        logger.info("Chatbot loaded successfully.")

    def _init_gemini(self) -> None:
        load_dotenv(Path(__file__).resolve().parent / ".env")
        self.gemini_api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.gemini_model_name = (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()

        if not self.gemini_api_key:
            self.gemini_error = "Gemini initialization skipped: GEMINI_API_KEY is missing from the environment."
            logger.warning(self.gemini_error)
            return

        # Log confirmation that a key was actually picked up, without ever
        # printing the key itself — useful for verifying "is my .env even
        # being read" without a debugger, while staying safe to leave in
        # production logs.
        if len(self.gemini_api_key) > 8:
            masked_key = f"{self.gemini_api_key[:4]}…{self.gemini_api_key[-4:]} ({len(self.gemini_api_key)} chars)"
        else:
            masked_key = "****"
        logger.info("GEMINI_API_KEY loaded from environment: %s", masked_key)

        if genai is None:
            self.gemini_error = (
                "Gemini SDK is not installed/importable ('google-generativeai'). "
                "Run `pip install google-generativeai` and restart the app."
            )
            logger.warning(self.gemini_error)
            return

        # Catch a still-configured, now-retired model before it ever makes
        # a request, rather than letting every single chat message fail
        # with a "quota exceeded" error that's actually a shutdown, not a
        # rate limit (see DEPRECATED_GEMINI_MODELS above for why the two
        # look identical in the logs).
        if self.gemini_model_name in DEPRECATED_GEMINI_MODELS:
            retirement_reason = DEPRECATED_GEMINI_MODELS[self.gemini_model_name]
            logger.warning(
                "GEMINI_MODEL is set to '%s', which is %s and can no longer serve requests "
                "(this is what produces a 429 with a free-tier 'limit: 0' on every call, "
                "which looks like ordinary throttling but never recovers). Automatically "
                "using '%s' instead for this run. To silence this warning, update GEMINI_MODEL "
                "in your .env file.",
                self.gemini_model_name, retirement_reason, FALLBACK_GEMINI_MODEL,
            )
            self.gemini_model_name = FALLBACK_GEMINI_MODEL

        try:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
            print("Model:", self.gemini_model_name)
            self.gemini_ready = True
            logger.info("Gemini initialized successfully using model '%s'.", self.gemini_model_name)
        except Exception as exc:
            classification = _classify_gemini_exception(exc)
            self.gemini_error = f"Gemini SDK initialization failed ({classification['status']}): {exc}"
            logger.exception("Gemini initialization failed: %s", self.gemini_error)

    def confidence_score(self, logits):
        probs = F.softmax(logits, dim=1)
        confidence = torch.max(probs).item()
        return confidence * 100

    def _find_best_dataset_match(self, vector) -> Dict[str, Any]:
        query_text = vector if isinstance(vector, str) else str(vector or "")
        results = search_semantic(query_text, top_k=1)

        if not results:
            return {
                "index": None,
                "similarity": 0.0,
                "matched_question": None,
                "matched_category": None,
                "answer": "",
            }

        best_result = results[0]
        best_similarity = float(best_result.get("score", 0.0))
        return {
            "index": best_result.get("row_index"),
            "similarity": best_similarity,
            "matched_question": best_result.get("question"),
            "matched_category": best_result.get("category"),
            "answer": best_result.get("answer"),
        }

    def _get_relevant_context(self, question: str) -> tuple[str, bool, float]:
        """Retrieve the top-K most similar dataset rows for ``question``.

        Returns a tuple of ``(context_text, is_relevant, best_similarity)``. When the best
        match falls below ``CONTEXT_RELEVANCE_THRESHOLD`` the question is treated as
        unrelated to the university knowledge base, and ``is_relevant`` is False so callers
        can tell Gemini to rely on its own general knowledge instead of forcing campus data
        into the answer.
        """
        results = search_semantic(question, top_k=TOP_K_CONTEXT_ROWS)
        best_similarity = float(results[0].get("score", 0.0)) if results else 0.0
        if not results or best_similarity < CONTEXT_RELEVANCE_THRESHOLD:
            logger.info("Semantic retrieval rejected context for question=%s | top_score=%s", question, best_similarity)
            return "", False, best_similarity

        context_lines = []
        for result in results:
            context_lines.append(
                f"Category: {result.get('category', '')}\n"
                f"Question: {result.get('question', '')}\n"
                f"Answer guidance: {result.get('answer', '')}"
            )

        logger.info(
            "Semantic retrieval accepted question=%s | top_result=%s | similarity=%s | context_passed=%s",
            question,
            results[0].get("question"),
            best_similarity,
            bool(context_lines),
        )
        return "\n\n".join(context_lines), True, best_similarity

    def _extract_doc_text(self, uploaded_file) -> str:
        if not uploaded_file or not getattr(uploaded_file, "filename", None):
            return ""

        filename = (uploaded_file.filename or "").lower()
        content = uploaded_file.read()
        uploaded_file.stream.seek(0)

        if filename.endswith(".txt"):
            return content.decode("utf-8", errors="ignore")

        if filename.endswith(".docx"):
            try:
                document = DocxDocument(io.BytesIO(content))
                return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
            except Exception as exc:
                logger.warning("Unable to parse DOCX: %s", exc)
                return ""

        if filename.endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(content))
                pages = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    pages.append(page_text)
                return "\n".join(page for page in pages if page.strip())
            except Exception as exc:
                logger.warning("Unable to parse PDF: %s", exc)
                return ""

        return ""

    def _build_history_context(self, conversation_history: Optional[List[Dict[str, Any]]] = None) -> str:
        if not conversation_history:
            return "No prior conversation context."

        lines = []
        for item in conversation_history[-6:]:
            if item.get("question"):
                lines.append(f"User: {item['question']}")
            if item.get("answer"):
                lines.append(f"Assistant: {item['answer']}")
        return "\n".join(lines)

    def _build_gemini_prompt(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        uploaded_text: str = "",
        user_name: str = "",
    ) -> str:
        context, is_relevant, _ = self._get_relevant_context(question)
        history = self._build_history_context(conversation_history)
        logger.info("Gemini prompt context passed: %s", bool(context and is_relevant))

        first_response_hint = (
            "This is the first assistant response in a new conversation. Begin with a warm, personalized welcome. "
            "Use the student's name if available."
            if not conversation_history else
            "This is a continuation of an existing conversation. Do not greet again or reintroduce yourself."
        )

        student_profile = (
            f"Student name: {user_name}\n"
            if user_name else
            "Student name: not provided\n"
        )

        if is_relevant:
            context_block = (
                "Campus knowledge context: RELEVANT\n"
                f"{context}"
            )
        else:
            context_block = (
                "Campus knowledge context: NOT RELEVANT (this question is not about "
                "university-specific data — answer using your own general knowledge and do "
                "not reference the context below or the university at all)\n"
                f"{context}"
            )

        return (
            f"{GEMINI_SYSTEM_PROMPT}\n\n"
            f"{first_response_hint}\n\n"
            f"{student_profile}\n"
            f"{context_block}\n\n"
            f"Conversation history:\n{history or 'No prior conversation history.'}\n\n"
            f"Uploaded document content (if any):\n{uploaded_text}\n\n"
            f"Student question: {question}"
        )

    def _call_gemini(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        uploaded_files: Optional[List[Any]] = None,
        user_name: str = "",
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Call Gemini and return ``(answer, error_info)``.

        Exactly one of the two is set on return: ``answer`` is a non-empty,
        non-whitespace string on success, or ``error_info`` is the
        classification dict from ``_classify_gemini_exception`` (or an
        equivalent hand-built dict for the non-exception failure modes
        below, like "not configured" or "empty response").
        """
        if not self.gemini_ready or self.gemini_model is None:
            reason = self.gemini_error or "Gemini was not initialized."
            logger.warning("Gemini call skipped: %s", reason)
            return None, {"status": "not_configured", "message": reason, "retry_after": None}

        extracted_text_chunks: List[str] = []
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if not uploaded_file or not getattr(uploaded_file, "filename", None):
                    continue
                filename = (uploaded_file.filename or "").lower()
                if filename.endswith((".png", ".jpg", ".jpeg")):
                    extracted_text_chunks.append(
                        f"Attached image: {filename}. The image was provided for reference, but the prompt is grounded using the uploaded document text and the CampusMate knowledge context."
                    )
                    continue

                extracted_text = self._extract_doc_text(uploaded_file)
                if extracted_text:
                    extracted_text_chunks.append(f"Document content for {filename}:\n{extracted_text}")

        prompt = self._build_gemini_prompt(
            question,
            conversation_history,
            "\n\n".join(extracted_text_chunks),
            user_name=user_name,
        )

        try:
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.55,
                    top_k=40,
                    top_p=0.95,
                    max_output_tokens=1536,
                ),
            )
        except Exception as exc:
            classification = _classify_gemini_exception(exc)
            logger.exception("Gemini request failed (%s): %s", classification["status"], exc)
            return None, classification

        # response.text is a *property* on the SDK's response object, not a
        # plain attribute — if Gemini blocked the output (safety filters,
        # no candidates returned, etc.) accessing it raises ValueError
        # rather than being missing. getattr(..., default) only guards
        # against AttributeError, so it silently does NOT catch that case;
        # this try/except is what actually does.
        try:
            answer = getattr(response, "text", "") or ""
        except Exception as exc:
            logger.warning("Gemini response could not be read as text (likely content filtering): %s", exc)
            return None, {
                "status": "content_blocked",
                "message": "Gemini declined to answer this request",
                "retry_after": None,
            }

        # A whitespace-only string is not a usable answer — treat it the
        # same as a genuinely empty response rather than sending blank
        # text to the student as if Gemini had succeeded.
        if answer.strip():
            return answer.strip(), None

        reason = "Gemini returned an empty response body."
        logger.warning(reason)
        return None, {"status": "empty_response", "message": reason, "retry_after": None}

    def predict(self, question: str) -> Dict[str, Any]:
        cleaned = preprocess_text(question)
        vector = self.vectorizer.transform([cleaned]).toarray()

        tensor = torch.tensor(vector, dtype=torch.float32, device=self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            pred = torch.argmax(logits, dim=1).item()
            confidence = self.confidence_score(logits)

        intent = self.label_encoder.inverse_transform([pred])[0]

        if cleaned in self.known_question_lookup:
            matched_row = self.df.iloc[self.known_question_lookup[cleaned]]
            return {
                "question": question,
                "intent": matched_row["category"],
                "confidence": f"{confidence:.2f}%",
                "matched_question": matched_row["question"],
                "answer": matched_row["answer"],
            }

        match = self._find_best_dataset_match(question)
        similarity = match["similarity"]
        if similarity >= SIMILARITY_THRESHOLD or confidence >= CONFIDENCE_THRESHOLD:
            return {
                "question": question,
                "intent": match["matched_category"],
                "confidence": f"{confidence:.2f}%",
                "matched_question": match["matched_question"],
                "answer": match["answer"],
            }

        return {
            "question": question,
            "intent": intent,
            "confidence": f"{confidence:.2f}%",
            "matched_question": None,
            "answer": "Sorry, I could not understand your question. Please contact the administration.",
        }

    def _get_safe_fallback_answer(self, fallback_response: Optional[Dict[str, Any]], status: Optional[str] = None) -> str:
        """Return a user-friendly fallback answer that never exposes Gemini/API internals."""
        fallback_answer = (fallback_response or {}).get("answer") or ""
        if not fallback_answer:
            return "I'm having trouble generating a response right now. Please try again in a moment."

        cleaned = fallback_answer.strip()
        lowered = cleaned.lower()

        if not cleaned:
            return "I'm having trouble generating a response right now. Please try again in a moment."

        if (
            "gemini" in lowered and (
                "quota" in lowered
                or "api" in lowered
                or "model" in lowered
                or "backend" in lowered
                or "error" in lowered
                or "rate limit" in lowered
                or "technical" in lowered
            )
        ):
            return "I’m having trouble generating a response right now. Please try again in a moment."

        if lowered.startswith("sorry, i could not understand"):
            return "I’m having trouble answering that clearly right now. Please try again in a moment."

        return cleaned

    def answer_question(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        uploaded_files: Optional[List[Any]] = None,
        user_name: str = "",
    ) -> Dict[str, Any]:
        if not self.gemini_ready or self.gemini_model is None:
            reason = self.gemini_error or "Gemini not initialized"
            logger.warning("Gemini fallback used because: %s", reason)
            response = self.predict(question)
            response["source"] = "ML"
            response["gemini_status"] = "not_configured"
            response["gemini_message"] = "Gemini is not configured on this server."
            response["error"] = reason
            return response

        gemini_answer, gemini_error = self._call_gemini(
            question,
            conversation_history=conversation_history,
            uploaded_files=uploaded_files,
            user_name=user_name,
        )
        if gemini_answer:
            response = {
                "question": question,
                "intent": "Gemini-generated",
                "confidence": "N/A",
                "matched_question": None,
                "answer": gemini_answer,
                "source": "Gemini",
                "gemini_status": "ok",
            }
            logger.info("Final answer source=Gemini | question=%s", question)
            return response

        # gemini_answer is falsy, so gemini_error is guaranteed to be set —
        # _call_gemini's contract is "exactly one of the two is non-None".
        status = gemini_error["status"]
        message = gemini_error["message"]
        retry_after = gemini_error.get("retry_after")

        logger.warning("Gemini returned a failure reason (%s): %s", status, message)
        response = self.predict(question)
        response["gemini_status"] = status
        response["gemini_message"] = "Unable to generate a response right now."
        response["error"] = "Unable to generate a response right now."
        response["source"] = "ML"

        fallback_answer = self._get_safe_fallback_answer(response, status)
        response["answer"] = fallback_answer

        logger.info("Final answer source=ML | question=%s", question)
        return response
