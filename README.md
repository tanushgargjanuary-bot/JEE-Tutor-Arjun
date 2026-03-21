# 🏹 Arjun: Socratic JEE Mentor

Arjun is a specialized AI reasoning engine designed to solve the "Doubt-Solving Gap" for JEE aspirants. Unlike general-purpose LLMs that simply dump answers, Arjun uses **Socratic Scaffolding** to build student intuition and **Visual Reasoning** to handle technical subjects like Organic Chemistry.

## 🚀 Key Features

* **Socratic Scaffolding:** Arjun refuses to provide direct answers. Instead, he provides hints, identifies conceptual gaps, and asks guided questions to lead students to the solution.
* **Visual Logic Engine:** Integrated SMILES rendering for Organic Chemistry structures and LaTeX for complex Physics/Math equations.
* **Performance Tracking:** Tracks student mastery levels via an internal SQLite layer to identify weak chapters.
* **Growth Loop:** Built-in referral system to reward top-tier students with "Pro" access.

## 🛠️ Technical Stack

* **Core:** Python & Streamlit
* **Reasoning:** Groq Llama-3.3-70b (Vertical Reasoning Logic)
* **Database:** SQLite (Stateful session & user data management)
* **UI:** Custom CSS & Streamlit Dialogs for enterprise feel

## 📦 Installation (Local Testing)

1. Clone the repository:
   ```bash
   git clone [https://github.com/tanushgargjanuary-bot/JEE-Tutor-Arjun.git](https://github.com/tanushgargjanuary-bot/JEE-Tutor-Arjun.git)
   
2. Install Dependencies
   pip install -r requirements.txt
   
4. Run the application
   streamlit run jee_tutor.py
