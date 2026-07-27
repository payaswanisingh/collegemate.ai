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

import numpy as np
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
from sklearn.metrics.pairwise import cosine_similarity

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
    "You are CampusMate AI, a warm, knowledgeable university assistant who talks like a "
    "helpful, articulate human — the same conversational quality students expect from "
    "ChatGPT or Gemini. You are NOT a lookup tool and you should NEVER sound like you are "
    "reading a line out of an FAQ database.\n\n"
    "You will be given three things: (1) 'Campus knowledge context' pulled from the "
    "university's internal records, (2) recent conversation history, and (3) the student's "
    "current question.\n\n"
    "How to use the campus knowledge context:\n"
    "- If context is marked as RELEVANT, treat it as trustworthy grounding for facts (fees, "
    "policies, dates, procedures, etc.), but rewrite and explain the information in your own "
    "natural words — never copy it verbatim or just restate a single line. Elaborate, "
    "clarify, and add helpful structure (headings/bullets) where useful.\n"
    "- If context is marked as NOT RELEVANT or absent, ignore it completely. This means the "
    "question is not about university-specific data, so answer it like a general-purpose "
    "AI assistant using your own broad knowledge — the same way you'd answer on any topic "
    "(technology, general knowledge, writing help, coding, current events, etc.). Do not "
    "mention the university or the knowledge base at all in that case.\n\n"
    "General style rules for every answer:\n"
    "- Sound natural, conversational, and professional — never robotic or templated.\n"
    "- Give a real explanation, not a one-liner, unless the student clearly just wants a "
    "quick fact.\n"
    "- Use short paragraphs, headings, and bullet points when it improves clarity, "
    "especially for multi-part or detailed answers.\n"
    "- When helpful, close with a brief summary or a suggestion for related information the "
    "student might want next.\n"
    "- Use the conversation history to understand follow-up questions (e.g. 'what about "
    "hostel fees?' or 'explain that more simply') without asking the student to repeat "
    "themselves."
)

CONFIDENCE_THRESHOLD = 15.0
SIMILARITY_THRESHOLD = 0.12
CONTEXT_RELEVANCE_THRESHOLD = 0.12
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
        similarity = cosine_similarity(vector, self.dataset_vectors)[0]
        best_index = int(np.argmax(similarity))
        best_similarity = float(similarity[best_index])
        matched_row = self.df.iloc[best_index]
        return {
            "index": best_index,
            "similarity": best_similarity,
            "matched_question": matched_row["question"],
            "matched_category": matched_row["category"],
            "answer": matched_row["answer"],
        }

    def _get_relevant_context(self, question: str) -> tuple[str, bool, float]:
        """Retrieve the top-K most similar dataset rows for ``question``.

        Returns a tuple of ``(context_text, is_relevant, best_similarity)``. When the best
        match falls below ``CONTEXT_RELEVANCE_THRESHOLD`` the question is treated as
        unrelated to the university knowledge base, and ``is_relevant`` is False so callers
        can tell Gemini to rely on its own general knowledge instead of forcing campus data
        into the answer.
        """
        cleaned = preprocess_text(question)
        vector = self.vectorizer.transform([cleaned]).toarray()
        similarity = cosine_similarity(vector, self.dataset_vectors)[0]
        top_indices = np.argsort(similarity)[::-1][:TOP_K_CONTEXT_ROWS]
        best_similarity = float(similarity[top_indices[0]]) if len(top_indices) else 0.0
        is_relevant = best_similarity >= CONTEXT_RELEVANCE_THRESHOLD

        context_lines = []
        for idx in top_indices:
            row = self.df.iloc[int(idx)]
            context_lines.append(
                f"Category: {row['category']}\n"
                f"Question: {row['question']}\n"
                f"Answer guidance: {row['answer']}"
            )
        return "\n\n".join(context_lines), is_relevant, best_similarity

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
    ) -> str:
        context, is_relevant, _ = self._get_relevant_context(question)
        history = self._build_history_context(conversation_history)

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
            f"{context_block}\n\n"
            f"Conversation context:\n{history}\n\n"
            f"Uploaded document content (if any):\n{uploaded_text}\n\n"
            f"Student question: {question}"
        )

    def _call_gemini(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        uploaded_files: Optional[List[Any]] = None,
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

        prompt = self._build_gemini_prompt(question, conversation_history, "\n\n".join(extracted_text_chunks))

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

        match = self._find_best_dataset_match(vector)
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

    def answer_question(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        uploaded_files: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        response = self.predict(question)

        if not self.gemini_ready or self.gemini_model is None:
            reason = self.gemini_error or "Gemini not initialized"
            logger.warning("Gemini fallback used because: %s", reason)
            response["source"] = "ML"
            response["gemini_status"] = "not_configured"
            response["gemini_message"] = "Gemini is not configured on this server."
            response["error"] = reason
            # Keep whatever answer ``predict`` already produced (dataset match or the
            # "could not understand" message) as the fallback rather than surfacing an
            # internal configuration error to the student.
            return response

        gemini_answer, gemini_error = self._call_gemini(
            question,
            conversation_history=conversation_history,
            uploaded_files=uploaded_files,
        )
        if gemini_answer:
            response["intent"] = "Gemini-generated"
            response["confidence"] = "N/A"
            response["matched_question"] = None
            response["answer"] = gemini_answer
            response["source"] = "Gemini"
            response["gemini_status"] = "ok"
            return response

        # gemini_answer is falsy, so gemini_error is guaranteed to be set —
        # _call_gemini's contract is "exactly one of the two is non-None".
        status = gemini_error["status"]
        message = gemini_error["message"]
        retry_after = gemini_error.get("retry_after")

        logger.warning("Gemini returned a failure reason (%s): %s", status, message)
        response["gemini_status"] = status
        response["gemini_message"] = message
        response["error"] = message
        response["source"] = "ML"

        fallback_answer = response.get("answer") or (
            "Gemini is unavailable right now. Please try again in a moment."
        )

        # Quota exhaustion is the one failure mode that's both common (free
        # tier) and easy to mistake for "the chatbot is broken" if the UI
        # only shows the ML fallback answer with no explanation. Prefixing
        # the answer itself guarantees the message shows up wherever the
        # frontend renders `answer`, without requiring any frontend changes.
        if status == "quota_exceeded":
            if retry_after:
                retry_note = f" Please try again in about {int(retry_after) + 1} seconds."
            else:
                retry_note = " Please try again in a few minutes."
            response["answer"] = (
                "⚠️ Gemini quota exceeded." + retry_note +
                " Here's an answer from our knowledge base in the meantime:\n\n" +
                fallback_answer
            )
        else:
            response["answer"] = fallback_answer

        return response
