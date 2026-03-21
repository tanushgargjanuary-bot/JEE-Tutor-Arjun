"""
Google OAuth Authentication for Arjun
Uses streamlit-google-auth for popup-style account selector

Setup Instructions:
1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URI: https://your-app.streamlit.app
6. Copy Client ID and Client Secret to .streamlit/secrets.toml

secrets.toml format:
[google]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
redirect_uri = "https://your-app.streamlit.app"
"""

import os
import streamlit as st


def get_google_client_id():
    """Get Google OAuth Client ID from secrets or environment."""
    try:
        return st.secrets["google"]["client_id"]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.getenv("GOOGLE_CLIENT_ID")


def get_google_client_secret():
    """Get Google OAuth Client Secret from secrets or environment."""
    try:
        return st.secrets["google"]["client_secret"]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.getenv("GOOGLE_CLIENT_SECRET")


def get_redirect_uri():
    """Get OAuth redirect URI."""
    try:
        return st.secrets["google"]["redirect_uri"]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.getenv("GOOGLE_REDIRECT_URI", "https://jee-tutor-arjun.streamlit.app")
