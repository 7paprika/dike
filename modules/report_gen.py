"""
Dike Volume Calculator — HTML Report Generator

Uses Jinja2 to render a professional A4 Calculation Sheet
with all input data, calculations, diagrams, and compliance checks.
"""

import os
import base64
from datetime import datetime
from typing import Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader
import plotly.graph_objects as go


from modules.calculator import REGULATIONS


def _fig_to_base64(fig: go.Figure, width: int = 800, height: int = 450) -> str:
    """Convert a Plotly figure to a base64-encoded PNG for HTML embedding."""
    try:
        img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
        return base64.b64encode(img_bytes).decode("ascii")
    except Exception:
        # If kaleido is not installed, return SVG as fallback
        try:
            svg_str = fig.to_image(format="svg", width=width, height=height).decode("utf-8")
            return base64.b64encode(svg_str.encode("utf-8")).decode("ascii")
        except Exception:
            return ""


def _fig_to_html_div(fig: go.Figure) -> str:
    """Convert a Plotly figure to an embedded HTML div string."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"displayModeBar": False, "staticPlot": True},
    )


def generate_report(
    project_info: dict,
    dike_params: dict,
    tanks_df: pd.DataFrame,
    calc_result,
    advanced: dict,
    plan_view_fig: Optional[go.Figure] = None,
    section_view_fig: Optional[go.Figure] = None,
    result_chart_fig: Optional[go.Figure] = None,
) -> str:
    """
    Render the HTML Calculation Sheet using Jinja2 template.

    Returns:
        HTML string ready for download.
    """
    # Locate template directory
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report_template.html")

    # Load custom CSS
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
    custom_css = ""
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            custom_css = f.read()

    # Convert figures to HTML divs for embedding
    plan_view_html = _fig_to_html_div(plan_view_fig) if plan_view_fig else ""
    section_view_html = _fig_to_html_div(section_view_fig) if section_view_fig else ""
    result_chart_html = _fig_to_html_div(result_chart_fig) if result_chart_fig else ""

    # Tank data as list of dicts
    tanks_data = tanks_df.to_dict(orient="records") if not tanks_df.empty else []

    # Deductions total
    deductions_total = (
        calc_result.V_sub_tanks
        + calc_result.V_foundations
        + calc_result.V_piping
        + calc_result.V_slope
    )

    # Clearance data
    clearance_data = []
    for c in calc_result.clearances:
        clearance_data.append({
            "item_a": c.item_a,
            "item_b": c.item_b,
            "distance": f"{c.distance:.3f}",
            "min_required": f"{c.min_required:.1f}",
            "status": "PASS" if c.is_pass else "FAIL",
            "is_pass": c.is_pass,
        })

    # Regulation info
    reg = REGULATIONS.get(
        getattr(calc_result, 'regulation_key', 'kosha'),
        REGULATIONS["kosha"]
    )
    volume_factor = getattr(calc_result, 'volume_factor', 1.0)
    volume_factor_pct = int(volume_factor * 100)

    # Render
    html = template.render(
        # Project
        project_name=project_info.get("project_name", "N/A"),
        doc_no=project_info.get("doc_no", "N/A"),
        engineer_name=project_info.get("engineer_name", "N/A"),
        date=datetime.now().strftime("%Y-%m-%d"),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        # Regulation
        regulation_name=reg["name"],
        regulation_short_name=reg["short_name"],
        regulation_authority=reg["authority"],
        regulation_target=reg["target"],
        volume_factor=volume_factor,
        volume_factor_pct=volume_factor_pct,

        # Dike
        dike_L=dike_params.get("L", 0),
        dike_W=dike_params.get("W", 0),
        dike_H=dike_params.get("H_dike", 0),

        # Tanks
        tanks=tanks_data,
        tank_count=len(tanks_data),

        # Calculation results
        V_dike=f"{calc_result.V_dike:,.2f}",
        V_req=f"{calc_result.V_req:,.2f}",
        V_req_factored=f"{getattr(calc_result, 'V_req_factored', calc_result.V_req):,.2f}",
        largest_tank=calc_result.largest_tank_name,
        V_sub_tanks=f"{calc_result.V_sub_tanks:,.2f}",
        V_foundations=f"{calc_result.V_foundations:,.2f}",
        V_piping=f"{calc_result.V_piping:,.2f}",
        V_rain=f"{calc_result.V_rain:,.2f}",
        V_fire=f"{calc_result.V_fire:,.2f}",
        V_margin=f"{calc_result.V_margin:,.2f}",
        margin_method=calc_result.margin_method.upper(),
        V_slope=f"{calc_result.V_slope:,.2f}",
        V_eff=f"{calc_result.V_eff:,.2f}",
        V_required_total=f"{calc_result.V_required_total:,.2f}",
        deductions_total=f"{deductions_total:,.2f}",
        is_pass=calc_result.is_pass,
        margin_pct=f"{calc_result.margin_pct:+.1f}",

        # Advanced inputs
        advanced=advanced,

        # Clearances
        clearances=clearance_data,

        # Diagrams (HTML divs)
        plan_view_html=plan_view_html,
        section_view_html=section_view_html,
        result_chart_html=result_chart_html,

        # Custom CSS
        custom_css=custom_css,
    )

    return html
