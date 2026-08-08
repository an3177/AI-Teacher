# AI Teacher
An AI-powered tutoring assistant that helps students learn concepts interactively through speech-to-text and chatbot feedback.

## Description
Toos and Languages Used: HTML, CSS, JavaScript, FastAPI, SQL, API: Groq

The user picks out a background, four are given, based on what type of environment they need. The user can either ask about a concept or explain one such as recursion or derivatives. Based on what the user says, the AI will explain the concept step-by-step or ask targeted questions. Based on responses it will corrects mistakes, give hints, and reinforce weak areas. This mimics how a real tutor teaches—not just giving solutions, but ensuring understanding. 

Python - The primary programming language used to implement the application's backend and to leverage AI services.
FastAPI - Python framework used to communicate with the AI, handle user requests, and return user responses to the frontend.
HTML/CSS/JS - Used to create the application UI and make it dynamic.
Groq API - Generates "teacher/tutor" like responses to the user based on what the user says.

## Getting Started

Before running the project, make sure you have:

- Python
- Git
- A Groq API key (or other LLM API key, depending on your configuration)

### Installation

1. Clone the respitory
  ```
  https://github.com/an3177/AI-Teacher.git
  ```
2. Install required packages
  ```
  pip install -r requirements.txt
  ```
3. Get and add your API key from https://console.groq.com/keys as well as your database url to .env.example:
  ```
  GROQ_API_KEY=your_groq_api_key_here
  DATABASE_URL=your_database_url_here
  ```
4. Run the application
   ```
   uvicorn app:app --reload
   ```


https://github.com/user-attachments/assets/85f6cdce-9d0c-42b3-88c8-9e64a6c7a49a

   
