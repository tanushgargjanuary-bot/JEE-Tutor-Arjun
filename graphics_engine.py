import json
import streamlit as st
import math

def render_fbd(json_data: str) -> None:
    """
    Renders a Physical Free Body Diagram (FBD) using SVG.
    
    Args:
        json_data: A JSON string defining the object and its forces.
        Format: {
            "object": "Block",
            "forces": [{"name": "mg", "angle": 270, "color": "red"}, ...]
        }
    """
    try:
        data = json.loads(json_data)
        forces = data.get("forces", [])
        obj_name = data.get("object", "Object")
        
        # SVG Constants
        width = 400
        height = 400
        center_x = width // 2
        center_y = height // 2
        arrow_len = 100
        
        svg_parts = []
        svg_parts.append(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">')
        
        # Draw Coordinate Grid (subtle)
        svg_parts.append(f'<line x1="0" y1="{center_y}" x2="{width}" y2="{center_y}" stroke="#eee" stroke-width="1" />')
        svg_parts.append(f'<line x1="{center_x}" y1="0" x2="{center_x}" y2="{height}" stroke="#eee" stroke-width="1" />')
        
        # Draw central object (a box)
        box_size = 60
        svg_parts.append(f'<rect x="{center_x - box_size//2}" y="{center_y - box_size//2}" width="{box_size}" height="{box_size}" fill="#eee" stroke="#333" stroke-width="2" rx="5" />')
        svg_parts.append(f'<text x="{center_x}" y="{center_y}" dominant-baseline="middle" text-anchor="middle" font-family="Arial" font-size="12" fill="#333">{obj_name}</text>')
        
        # Draw forces
        for force in forces:
            name = force.get("name", "")
            angle_deg = force.get("angle", 0)
            color = force.get("color", "red")
            
            # Convert angle to radians (SVG y increases downward, so we negate angle)
            # 0 deg is Right, 90 deg is Up (in math), so -90 in SVG
            angle_rad = math.radians(angle_deg)
            # Math y = sin(theta), SVG y = -sin(theta)
            end_x = center_x + arrow_len * math.cos(angle_rad)
            end_y = center_y - arrow_len * math.sin(angle_rad)
            
            # Draw line
            svg_parts.append(f'<line x1="{center_x}" y1="{center_y}" x2="{end_x}" y2="{end_y}" stroke="{color}" stroke-width="2" marker-end="url(#arrowhead-{color})" />')
            
            # Draw arrowhead definition (if needed)
            svg_parts.append(f'''
            <defs>
                <marker id="arrowhead-{color}" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="{color}" />
                </marker>
            </defs>
            ''')
            
            # Draw label at the tip
            label_offset = 20
            label_x = center_x + (arrow_len + label_offset) * math.cos(angle_rad)
            label_y = center_y - (arrow_len + label_offset) * math.sin(angle_rad)
            svg_parts.append(f'<text x="{label_x}" y="{label_y}" dominant-baseline="middle" text-anchor="middle" font-family="Arial" font-weight="bold" font-size="14" fill="{color}">{name}</text>')
            
        svg_parts.append('</svg>')
        
        # Wrap SVG in a styled div
        final_html = f"""
        <div style="display: flex; justify-content: center; background: white; padding: 20px; border-radius: 10px; border: 1px solid #ddd; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">
            {''.join(svg_parts)}
        </div>
        """
        st.components.v1.html(final_html, height=450)
        
    except Exception as e:
        st.error(f"Error rendering FBD: {str(e)}")

def extract_and_render_fbd(text: str) -> str:
    """Detects and renders fbd blocks."""
    import re
    pattern = r'```fbd\s*\n(.*?)```'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    if not matches:
        return text
    
    result = text
    for i, match in enumerate(reversed(matches)):
        json_str = match.group(1).strip()
        start, end = match.span()
        
        # Render
        render_fbd(json_str)
        
        # Replace template
        result = result[:start] + f"\n\n*[Proper FBD diagram rendered above]*\n\n" + result[end:]
        
    return result
