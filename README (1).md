# 🎓 CampusMate AI – Intelligent Student Support Chatbot

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web_Framework-black?style=for-the-badge&logo=flask)
![PyTorch](https://img.shields.io/badge/PyTorch-AI_Model-red?style=for-the-badge&logo=pytorch)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue?style=for-the-badge&logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

### 🚀 AI-Powered Student Assistance Platform with Secure Authentication

*A modern university chatbot that provides instant responses to student queries using Machine Learning while offering a secure user authentication system and premium user experience.*

</div>

---

# 📌 Overview

CampusMate AI is an intelligent student support platform built using **Flask**, **PyTorch**, **Machine Learning**, and **SQLite**.

Instead of searching through multiple university websites or waiting for administrative responses, students can simply ask questions in natural language and receive instant answers.

The system combines a **machine learning-based intent classification model** with a modern web interface and secure authentication to create a complete student assistance platform.

---

# ✨ Key Features

## 🤖 AI Chatbot

- Instant answers to student queries
- Machine Learning based intent prediction
- TF-IDF text vectorization
- PyTorch Neural Network model
- Confidence score prediction
- Natural language understanding

---

## 🔐 Authentication System

- Secure User Registration
- Login & Logout
- Password Hashing
- Session Management
- Protected Chatbot Access
- SQLite User Database

---

## 👨‍🎓 Multi User Registration

Supports multiple user categories:

- College Students
- School Students
- Parents

Each registration form dynamically changes according to the selected user type.

---

## 🎨 Modern User Interface

- Premium Dark Theme
- Glassmorphism Design
- Responsive Layout
- Animated Components
- Interactive Dashboard
- Clean User Experience

---

## 📚 Student Support Categories

The chatbot can answer questions related to:

- Admission
- Fees
- Scholarships
- Attendance
- Examination
- Academic Calendar
- Hostel
- Placements
- Library
- Departments
- Courses
- Certificates
- Documents
- Faculty Information

---

# 🛠 Technology Stack

| Category | Technologies |
|----------|--------------|
| Backend | Flask |
| Machine Learning | PyTorch |
| NLP | TF-IDF Vectorizer |
| Database | SQLite |
| Authentication | Flask Login |
| ORM | Flask SQLAlchemy |
| Frontend | HTML5, CSS3, JavaScript |
| Styling | Glassmorphism UI |
| Model Training | Scikit-Learn |

---

# 📂 Project Structure

```text
CampusMate-AI/
│
├── app.py
├── chatbot.py
├── model.py
├── utils.py
├── train.py
├── data.csv
├── requirements.txt
├── extensions.py
│
├── auth/
│   ├── __init__.py
│   ├── routes.py
│   ├── user_model.py
│   └── validators.py
│
├── models/
│   ├── chatbot_model.pth
│   ├── vectorizer.pkl
│   └── label_encoder.pkl
│
├── templates/
│   ├── landing.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   └── index.html
│
├── static/
│   ├── style.css
│   ├── auth.css
│   ├── script.js
│   └── auth.js
│
└── README.md
```

---

# ⚙ Installation

## Clone Repository

```bash
git clone https://github.com/yourusername/CampusMate-AI.git

cd CampusMate-AI
```

---

## Create Virtual Environment

### Windows

```bash
python -m venv venv

venv\Scripts\activate
```

### Linux / Mac

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Train the AI Model

```bash
python train.py
```

This generates:

```
models/
│
├── chatbot_model.pth
├── vectorizer.pkl
└── label_encoder.pkl
```

---

## Run the Application

```bash
python app.py
```

Application starts on

```
http://localhost:5000
```

---

# 🚀 Application Flow

```text
Landing Page
       │
       ▼
 Login / Register
       │
       ▼
 Dashboard
       │
       ▼
 AI Chatbot
       │
       ▼
 Instant Student Assistance
```

---

# 🔒 Authentication Features

✔ Secure Password Hashing

✔ Session-Based Login

✔ Protected Routes

✔ Login Validation

✔ Registration Validation

✔ Dynamic User Forms

✔ Logout Functionality

---

# 🧠 Machine Learning Pipeline

```
User Question
        │
        ▼
Text Cleaning
        │
        ▼
TF-IDF Vectorization
        │
        ▼
PyTorch Neural Network
        │
        ▼
Intent Prediction
        │
        ▼
Answer Retrieval
```

---

# 📡 API Endpoints

| Method | Endpoint | Description |
|----------|----------|-------------|
| GET | / | Landing Page |
| GET | /login | Login Page |
| GET | /register | Registration Page |
| GET | /dashboard | User Dashboard |
| GET | /app | AI Chat Interface |
| POST | /chat | Chatbot Prediction |
| POST | /predict | Legacy Prediction |
| GET | /health | Health Check |

---

# 📸 Screens

- Landing Page
- Login
- Register
- Dashboard
- AI Chat Interface

*(Add screenshots here after uploading images.)*

---

# 🔮 Future Enhancements

- Chat History
- Profile Management
- Admin Dashboard
- Multi-University Support
- Voice Chat
- Multilingual Support
- Generative AI Integration
- RAG-based Knowledge Retrieval
- PDF Question Answering
- Email Notifications

---

# 🎯 Learning Outcomes

This project demonstrates:

- Machine Learning Integration
- Natural Language Processing
- Flask Backend Development
- Authentication & Authorization
- Database Management
- REST API Development
- Frontend UI/UX Design
- Software Architecture
- Secure Password Management

---

# 👩‍💻 Developed By

**Payaswani Singh**

B.Tech – Computer Science (IoT)

Passionate about Artificial Intelligence, Machine Learning, and Full Stack Development.

---

# ⭐ If you like this project

Give this repository a ⭐ on GitHub!