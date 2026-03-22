"""
Mermaid.js Renderer for Streamlit

Renders Mermaid.js diagrams from markdown code blocks using CDN.
Uses st.components.v1.html for proper rendering.
"""

import re
import streamlit as st

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"


def render_mermaid(diagram_code: str, key: str = "0") -> None:
    """
    Render a Mermaid.js diagram in Streamlit using HTML component.

    Args:
        diagram_code: The Mermaid diagram definition (without ```mermaid wrappers)
        key: Unique key for this diagram instance
    """
    # Escape special characters for HTML/JS
    safe_code = (
        diagram_code
        .replace('"', '&quot;')
        .replace('\n', '\\n')
        .replace('\\', '\\\\')
    )

    html = f"""
    <div id="mermaid-container-{key}" style="text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px;">
        <div class="mermaid" id="mermaid-{key}">
            {safe_code}
        </div>
    </div>
    <script src="{MERMAID_CDN}"></script>
    <script>
        (function() {{
            // Configure mermaid
            mermaid.initialize({{ 
                startOnLoad: false, 
                theme: 'default',
                securityLevel: 'loose',
            }});
            
            // Render this specific diagram
            const element = document.getElementById('mermaid-{key}');
            if (element) {{
                mermaid.run({{
                    nodes: [element]
                }});
            }}
        }})();
    </script>
    """
    st.components.v1.html(html, height=500)


def extract_and_render_mermaid(text: str, container=None) -> str:
    """
    Find all ```mermaid blocks in text and render them as interactive diagrams.

    Args:
        text: The full response text potentially containing mermaid code blocks
        container: Optional Streamlit container for rendering (default: current position)

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

        # Remove the code block from text (replace with placeholder)
        result = result[:start] + \
            f"\n\n*[Diagram {idx + 1} rendered above]*\n\n" + result[end:]

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
