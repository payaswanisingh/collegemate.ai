# chatbot.py

"""
High-level wrapper that loads the trained PyTorch model,
TF-IDF vectorizer and label encoder, and provides prediction.
"""

import io
import logging
import os
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

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
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

        if genai is None:
            self.gemini_error = (
                "Gemini SDK is not installed/importable ('google-generativeai'). "
                "Run `pip install google-generativeai` and restart the app."
            )
            logger.warning(self.gemini_error)
            return

        try:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
            self.gemini_ready = True
            logger.info("Gemini initialized successfully using model '%s'.", self.gemini_model_name)
        except Exception as exc:
            self.gemini_error = f"Gemini SDK initialization failed: {exc}"
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
    ) -> tuple[Optional[str], Optional[str]]:
        if not self.gemini_ready or self.gemini_model is None:
            reason = self.gemini_error or "Gemini was not initialized."
            logger.warning("Gemini call skipped: %s", reason)
            return None, reason

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
            answer = getattr(response, "text", "")
            if answer:
                return answer.strip(), None

            reason = "Gemini returned an empty response body."
            logger.warning(reason)
            return None, reason
        except Exception as exc:
            reason = f"Gemini request failed: {exc}"
            logger.exception(reason)
            return None, reason

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
            response["answer"] = gemini_answer.strip()
            response["source"] = "Gemini"
            return response

        if gemini_error:
            logger.warning("Gemini returned a failure reason: %s", gemini_error)
            response["error"] = gemini_error

        response["source"] = "ML"
        response["answer"] = response.get("answer") or "Gemini is unavailable right now. Please try again in a moment."
        return response