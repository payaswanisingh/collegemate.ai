# chatbot.py

"""
High-level wrapper that loads the trained PyTorch model,
TF-IDF vectorizer and label encoder, and provides prediction.
"""

import logging
from typing import Any, Dict

import numpy as np
import torch
import torch.nn.functional as F
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

# ------------------------------------------------------------------
# Static Answers
# ------------------------------------------------------------------

ANSWER_MAP = {
    "Fee Structure": "The fee structure varies by program. Please check the official university fee structure on the student portal.",

    "Exam Dates": "Examination dates are available in the academic calendar and on the university examination portal.",

    "Attendance Policy": "Students must maintain at least 75% attendance to be eligible for semester examinations.",

    "Leave Application": "Leave applications can be submitted through the student portal or your department office.",

    "Library Timings": "The library is open from 8:00 AM to 9:00 PM on working days.",

    "Hostel Facilities": "The university hostel provides accommodation, Wi-Fi, mess facilities, and 24x7 security. Contact the hostel office for fee and room allotment details.",

    "Placement Cell": "The placement cell conducts training sessions, internships, and campus recruitment drives throughout the academic year.",

    "Scholarships": "Students can apply for scholarships through the university scholarship portal if they meet the eligibility criteria.",

    "Faculty Details": "Faculty information is available on the official department webpage.",

    "Academic Calendar": "The academic calendar contains semester schedules, holidays, examination dates, and important academic events.",

    "Sports Facilities": "The university provides sports facilities including cricket, football, badminton, basketball, volleyball, and indoor games.",

    "Transport Services": "University buses operate on multiple routes. Bus timings and routes are available on the transport office webpage.",

    "Admission Process": "You can apply through the university admission portal. Fill out the application form, upload the required documents, and submit the application before the deadline.",

    "ID Card Issues": "If your ID card is lost or damaged, contact the student administration office to request a replacement.",

    "Internship Support": "The Training and Placement Cell assists students with internship opportunities and industry collaborations.",

    "Course Registration": "Course registration can be completed through the student portal during the registration period.",

    "Result Declaration": "Semester results are published on the university student portal after evaluation is completed.",

    "Lab Facilities": "Laboratories are equipped with the required software and hardware for practical sessions.",

    "Student Clubs": "Students can join technical, cultural, sports, and social clubs through the student activities office.",

    "Campus Rules": "Students are expected to follow the university code of conduct, maintain discipline, and comply with campus regulations."
}


class Chatbot:

    def __init__(self):

        self.device = get_device()
        logger.info(f"Using device: {self.device}")

        # ----------------------------
        # Load Vectorizer
        # ----------------------------
        self.vectorizer = load_vectorizer()

        # ----------------------------
        # Load Label Encoder
        # ----------------------------
        self.label_encoder = load_label_encoder()

        # ----------------------------
        # Model Dimensions
        # ----------------------------
        input_dim = len(self.vectorizer.get_feature_names_out())
        num_classes = len(self.label_encoder.classes_)

        # ----------------------------
        # Load Model
        # ----------------------------
        self.model = load_model(
            ChatbotModel,
            input_dim=input_dim,
            num_classes=num_classes,
            path=MODEL_PATH,
            device=self.device,
        )

        # ----------------------------
        # Load Dataset
        # ----------------------------
        self.df = load_dataset()

        logger.info("Chatbot loaded successfully.")

    def confidence_score(self, logits):

        probs = F.softmax(logits, dim=1)
        confidence = torch.max(probs).item()

        return confidence * 100

    def predict(self, question: str) -> Dict[str, Any]:

        cleaned = preprocess_text(question)

        vector = self.vectorizer.transform([cleaned]).toarray()

        tensor = torch.tensor(
            vector,
            dtype=torch.float32,
            device=self.device,
        )

        with torch.no_grad():

            logits = self.model(tensor)

            pred = torch.argmax(logits, dim=1).item()

            confidence = self.confidence_score(logits)

        intent = self.label_encoder.inverse_transform([pred])[0]

        if confidence < 70:

            return {
                "question": question,
                "intent": intent,
                "confidence": f"{confidence:.2f}%",
                "matched_question": None,
                "answer": "Sorry, I could not understand your question. Please contact the administration.",
            }

        subset = self.df[self.df["category"] == intent]

        if subset.empty:

            return {
                "question": question,
                "intent": intent,
                "confidence": f"{confidence:.2f}%",
                "matched_question": None,
                "answer": ANSWER_MAP.get(intent, "Answer not available."),
            }

        processed_questions = subset["question"].apply(preprocess_text)

        candidate_vectors = self.vectorizer.transform(processed_questions).toarray()

        similarity = cosine_similarity(vector, candidate_vectors)[0]

        best_index = np.argmax(similarity)

        matched_question = subset.iloc[best_index]["question"]

        answer = ANSWER_MAP.get(intent, "Answer not available.")

        return {
            "question": question,
            "intent": intent,
            "confidence": f"{confidence:.2f}%",
            "matched_question": matched_question,
            "answer": answer,
        }