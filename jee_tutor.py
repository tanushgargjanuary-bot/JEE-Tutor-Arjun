import streamlit as st
from groq import Groq
from fpdf import FPDF
import streamlit.components.v1 as components

# 1. INITIALIZATION (Security: Use st.secrets or rotate your key)
# Note: Replace this with your new, private key
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 2. MASTER QUALITY PROMPTS (High-Depth + Identity)
STRICT_GUARDRAIL = """
### CRITICAL RULES:
- NO PREAMBLE. NO CONVERSATIONAL FLUFF.
- SELF-VERIFICATION: Verify logic against JEE Advanced standards before outputting.
- TERMINATE immediately after the technical explanation.
"""

PROMPTS = {
    "CHEMISTRY": f"""You are a JEE Chemistry Specialist (AIR < 100). 
- REASONING: Focus on Electronic Effects (Resonance > Hyperconjugation > Inductive).
- VISUALS: Use Mermaid.js (graph LR) for reaction maps.
- GROUNDING: Cite NCERT Class 11/12 Units.
{STRICT_GUARDRAIL}""",

    "PHYSICS": f"""You are a JEE Physics Specialist (AIR < 100). 
- REASONING: Start from fundamental laws. Use Variable Extraction first.
- VISUALS: Describe FBD setup in Mermaid.js.
{STRICT_GUARDRAIL}""",

    "MATHEMATICS": f"""You are a JEE Mathematics Specialist (AIR < 100). 
- REASONING: State Domain/Range and check for boundary edge cases (0, infinity).
- VISUALS: Use LaTeX for every single step.
{STRICT_GUARDRAIL}""",

    "GENERAL": f"""You are the JEE Vertical Reasoning Engine (AIR < 100 Coach).

### INTENT HANDLING:
1. GREETING (Hi/Hello): Reply with a professional welcome. State you are a specialized JEE Reasoning Engine. Ask for a Physics, Chemistry, or Math query.
2. IDENTITY (Who are you?): Explain your 'Vertical Reasoning' edge, NCERT grounding, and 'Trap Detection' logic.
3. SYLLABUS/STRATEGY: Provide granular tables for weightage and 5-year trend analysis.

{STRICT_GUARDRAIL}"""
}

# 3. SMARTER ROUTER (Fixed 'Hi' and 'Syllabus' misfires)
def route_subject(user_query):
    query_lower = user_query.strip().lower()
    
    # Intent 1: Greetings & Short Talk
    greetings = ["hi", "hello", "hey", "who are you", "what is this"]
    if query_lower in greetings or len(query_lower) < 4:
        return "GENERAL"
        
    # Intent 2: Administrative/Strategy
    admin_triggers = ["syllabus", "date", "weightage", "tips", "strategy", "prep", "how to"]
    if any(trigger in query_lower for trigger in admin_triggers):
        return "GENERAL"
    
    # Intent 3: Technical Subject Routing (AI-Powered)
    classification = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.0, # Purely deterministic routing
        messages=[{"role": "system", "content": "Classify: PHYSICS, CHEMISTRY, or MATHEMATICS. Output ONLY one word."},
                  {"role": "user", "content": user_query}]
    )
    return classification.choices[0].message.content.strip().upper()

# 4. UTILITY FUNCTIONS
def copy_button(text):
    clean_text = text.replace("`", "\\`").replace("$", "\\$")
    button_html = f"""
        <script>
        function copyText() {{
            navigator.clipboard.writeText(`{clean_text}`).then(() => {{
                alert("Solution copied to clipboard!");
            }});
        }}
        </script>
        <button onclick="copyText()" style="
            background-color: #4CAF50; color: white; padding: 10px;
            border: none; border-radius: 5px; cursor: pointer; width: 100%;
        ">📋 Copy Solution</button>
    """
    components.html(button_html, height=60)

# 5. STREAMLIT INTERFACE
st.set_page_config(page_title="JEE Vertical Reasoner", layout="wide")
st.title("🚀 JEE Vertical Reasoning Engine")

user_input = st.text_area("Enter your JEE problem or ask about our edge:", height=150)

if st.button("Generate Expert Solution"):
    if user_input:
        with st.spinner("Analyzing via Multi-Agent Chain..."):
            subject = route_subject(user_input)
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0.2, # Stable, AIR < 100 quality
                messages=[
                    {"role": "system", "content": PROMPTS.get(subject, PROMPTS["GENERAL"])},
                    {"role": "user", "content": user_input}
                ]
            )
            
            response = completion.choices[0].message.content
            st.info(f"Expert Vertical Engaged: {subject}")
            st.markdown(response)
            
            st.divider()
            
            col1, col2 = st.columns(2)
            with col1:
                copy_button(response)
            with col2:
                st.download_button("📥 Download .txt", data=response, file_name="JEE_Solution.txt")
