"""
Mermaid.js Renderer for Streamlit

Renders Mermaid.js diagrams using st.components.v1.html with CDN.
"""

import re
import streamlit as st

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"


def render_mermaid(diagram_code: str, key: str = "0") -> None:
    """
    Render a Mermaid.js diagram using HTML component.

    Args:
        diagram_code: Mermaid diagram definition (without ```mermaid)
        key: Unique identifier for this diagram
    """
    # Clean the diagram code
    diagram_code = diagram_code.strip()

    # Create unique container ID
    container_id = f"mermaid_{key}_{id(diagram_code)}"

    html = f"""
    <div id="{container_id}" class="mermaid" style="text-align: center; background: #fafafa; padding: 20px; border-radius: 8px; border: 1px solid #eee;">
    {diagram_code}
    </div>
    <script src="{MERMAID_CDN}"></script>
    <script>
        (function() {{
            const container = document.getElementById('{container_id}');
            if (!container) return;
            
            // Check if mermaid is loaded
            if (typeof mermaid === 'undefined') {{
                console.log('Mermaid not loaded yet');
                return;
            }}
            
            // Initialize and render
            mermaid.initialize({{ 
                startOnLoad: false, 
                theme: 'default',
                securityLevel: 'loose',
            }});
            
            // Force re-render
            container.removeAttribute('data-processed');
            mermaid.run({{
                nodes: [container]
            }});
        }})();
    </script>
    """
    st.components.v1.html(html, height=400)


def extract_and_render_mermaid(text: str) -> str:
    """
    Find ```mermaid blocks and render them as diagrams.

    Args:
        text: Response text containing ```mermaid code blocks

    Returns:
        str: Text with mermaid blocks replaced by placeholders
    """
    pattern = r'```mermaid\s*\n(.*?)```'
    matches = list(re.finditer(pattern, text, re.DOTALL))

    if not matches:
        return text

    result = text
    for i, match in enumerate(reversed(matches)):
        idx = len(matches) - 1 - i
        diagram_code = match.group(1).strip()
        start, end = match.span()

        # Render the diagram
        render_mermaid(diagram_code, key=str(idx))

        # Replace with placeholder
        result = result[:start] + \
            f"\n\n*[Diagram {idx + 1} rendered above]*\n\n" + result[end:]

    return result


def extract_csv_coordinates(text: str) -> list:
    """Extract CSV coordinate blocks for graphing."""
    pattern = r'```csv\s*\n\s*x,y\s*\n((?:\s*[\d.\-]+,[\d.\-]+\s*\n?)+)'
    match = re.search(pattern, text)

    if not match:
        return []

    coords = []
    for line in match.group(1).strip().split('\n'):
        parts = line.strip().split(',')
        if len(parts) == 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass

    return coords


def remove_csv_blocks(text: str) -> str:
    """Remove CSV code blocks from text."""
    return re.sub(r'```csv\s*\n.*?```', '', text, flags=re.DOTALL)
