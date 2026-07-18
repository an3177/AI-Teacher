AI Teacher
An AI-powered tutoring assistant that helps students learn concepts interactively through speech-to-text and chatbot feedback.


How It's Made:
Tech used: HTML, CSS, JavaScript, FastAPI, SQL, API: Groq

User can either ask about a concept or explain one such as recursion and derivatives. Based on what you say, the AI will explain the concept step-by-step or ask targeted questions. Based on responses it will corrects mistakes, give hints, and reinforce weak areas.
This mimics how a real tutor teaches—not just giving solutions, but ensuring understanding.

During developlemt, I reduced response latency by restructuring how API calls are handled and optimized state management so the app updates smoothly without extra re-renders.

Lessons Learned:
Small changes in wording in prompts significantly affected whether the AI gave helpful explanations or ask good questions. More detailed prompts improved explanation quality but increased latency, so I had to find a balance.
