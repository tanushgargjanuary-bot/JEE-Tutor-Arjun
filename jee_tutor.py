import json
import osimport pandas as pd
import streamlit as stfrom groq import Groq
from database import (
    init_database, create_user, authenticate_user, get_user_by_id,
    has_submitted_feedback, submit_feedback, is_pro_user,
    apply_referral_code, get_db_connection, get_or_create_google_user,
)
from prompts import PROMPTS
from google_auth import get_google_client_id, get_google_client_secret, get_redirect_uri

import re

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"


def render_mermaid(diagram_code: str, key: str = "0") -> None:
    """
    Render a Mermaid.js diagram using HTML component.

    Args:
