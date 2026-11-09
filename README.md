# Arjun — JEE Study Assistant

Arjun is a Streamlit application that uses the Groq API to help students work through JEE questions. It routes questions to subject-specific prompts for Physics, Chemistry, Mathematics, or General guidance.

## Current features

- Subject routing for submitted questions.
- Groq-powered response generation.
- Streamlit user interface.
- SQLite-backed user and application data.
- Google sign-in integration.
- Mermaid and graphics rendering helpers.
- Optional admin access protected by a configured passcode.

The application depends on external API and authentication configuration. Model output can be wrong. Verify important solutions against trusted study material.

## Requirements

- Python 3.10 or later is recommended.
- A Groq API key.
- Google OAuth credentials if Google sign-in is enabled.

## Local setup

```bash
git clone https://github.com/tanushgargjanuary-bot/JEE-Tutor-Arjun.git
cd JEE-Tutor-Arjun

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Configure secrets

Create the Streamlit secrets directory:

```bash
mkdir .streamlit
```

Copy `secrets_template.toml` to `.streamlit/secrets.toml`. Add your own values. Do not commit the real secrets file.

At minimum, configure:

- `GROQ_API_KEY` — required for model requests.
- `ADMIN_PASSCODE` — optional. Set a new, strong value if you need admin access.
- Google OAuth values — required only when Google sign-in is used.

The app also supports environment variables for the Groq API key and admin passcode.

## Start the app

```bash
streamlit run jee_tutor.py
```

## Main files

| File | Purpose |
|---|---|
| `jee_tutor.py` | Streamlit application and request flow |
| `prompts.py` | Subject-specific prompt definitions |
| `database.py` | User and application database operations |
| `google_auth.py` | Google sign-in configuration |
| `graphics_engine.py` | Graphics-related helpers |
| `mermaid_renderer.py` | Mermaid and CSV rendering helpers |
| `requirements.txt` | Python dependencies |

## Security

- Keep API keys, OAuth credentials, and admin passcodes out of Git.
- Use a unique admin passcode. Do not reuse an exposed value.
- Rotate any credential that was previously committed.
- Never share a real `.streamlit/secrets.toml` file.

## Project status

This repository contains an application codebase. It has not been independently tested as part of this documentation update.
