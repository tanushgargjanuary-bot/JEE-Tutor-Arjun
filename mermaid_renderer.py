"""
Mermaid.js Renderer for Streamlit

Renders Mermaid.js diagrams from markdown code blocks using CDN.
"""

import re
import streamlit as st

MERMAID_CDN = "https://cdn.jsdelivr.net/gh/mermaid-js/mermaid@10/dist/mermaid.min.js"


def render_mermaid(diagram_code: str, key: str = "") -> None:
    """
    Render a Mermaid.js diagram in Streamlit.
    
    Args:
        diagram_code: The Mermaid diagram definition (without ```mermaid wrappers)
        key: Unique key for this diagram instance
    """
    # Escape special characters for HTML
    safe_code = diagram_code.replace('"', '&quot;').replace('\n', '\\n')
    
    html = f"""
    <div id="mermaid-{key}" class="mermaid" style="text-align: center; padding: 20px;">
    {safe_code}
    </div>
    <script src="{MERMAID_CDN}"></script>
    <script>
        // Initialize mermaid if not already done
        if (typeof mermaid === 'undefined') {{
            mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        }} else {{
            mermaid.init(undefined, document.getElementById('mermaid-{key}'));
        }}
    </script>
    """
    st.components.v1.html(html, height=400)


def extract_and_render_mermaid(text: str) -> str:
    """
    Find all ```mermaid blocks in text and render them as interactive diagrams.
    
    Returns the text with mermaid blocks replaced by rendered components.
    
    Args:
        text: The full response text potentially containing mermaid code blocks
        
    Returns:
        str: Text with mermaid blocks removed (they're rendered separately)
    """
    # Pattern to match ```mermaid ... ``` blocks
    pattern = r'```mermaid\n(.*?)```'
    
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    if not matches:
        return text
    
    # Process matches in reverse to maintain string positions
    result = text
    for i, match in enumerate(reversed(matches)):
        idx = len(matches) - 1 - i
        diagram_code = match.group(1).strip()
        start, end = match.span()
        
        # Render the mermaid diagram
        render_mermaid(diagram_code, key=f"mermaid_{idx}")
        
        # Remove the code block from text
        result = result[:start] + result[end:]
    
    return result


def extract_csv_coordinates(text: str) -> list:
    """
    Extract CSV-style coordinate blocks from text.
    
    Looks for blocks like:
    ```csv
    x,y
    0,0
    1,1
    ```
    
    Args:
        text: The response text potentially containing CSV coordinate blocks
        
    Returns:
        list: List of (x, y) tuples, empty if none found
    """
    pattern = r'```csv\s*\n\s*x,y\s*\n((?:\s*[\d.\-]+,[\d.\-]+\s*\n?)+)'
    match = re.search(pattern, text)
    
    if not match:
        return []
    
    coords = []
    for line in match.group(1).strip().split('\n'):
        parts = line.strip().split(',')
        if len(parts) == 2:
            try:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                coords.append((x, y))
            except ValueError:
                continue
    
    return coords


def remove_csv_blocks(text: str) -> str:
    """Remove CSV code blocks from text after extraction."""
    pattern = r'```csv\s*\n.*?\n```'
    return re.sub(pattern, '', text, flags=re.DOTALL)
