"""
Dike Volume Calculator — Layout Visualization

Generates Plan View (top-down) and Section View (elevation) using Plotly.
Shows dike boundary, tanks, clearance dimensions, and violation warnings.
"""

import math
from typing import List
import plotly.graph_objects as go
from modules.calculator import DikeInput, TankInput, ClearanceResult


# ─── Color Palette ───
COLORS = {
    "dike_fill": "rgba(180, 195, 210, 0.15)",
    "dike_line": "#5A7A9B",
    "tank_fill": "rgba(70, 130, 200, 0.25)",
    "tank_line": "#2E6BA6",
    "tank_label": "#1A3A5C",
    "dim_line": "#6B7B8D",
    "dim_text": "#3A4A5A",
    "violation_line": "#E53935",
    "violation_text": "#C62828",
    "ground_fill": "rgba(160, 140, 120, 0.2)",
    "ground_line": "#8D7B6A",
    "dike_wall_fill": "rgba(150, 150, 160, 0.5)",
    "submerged_fill": "rgba(255, 180, 60, 0.3)",
    "slope_fill": "rgba(200, 100, 80, 0.15)",
    "bg": "#FAFBFD",
    "grid": "#E8ECF0",
}


def _circle_points(cx: float, cy: float, r: float, n: int = 60) -> tuple:
    """Generate x, y points for a circle."""
    angles = [2 * math.pi * i / n for i in range(n + 1)]
    xs = [cx + r * math.cos(a) for a in angles]
    ys = [cy + r * math.sin(a) for a in angles]
    return xs, ys


def _add_dimension_line(
    fig: go.Figure,
    x0: float, y0: float,
    x1: float, y1: float,
    label: str,
    color: str = COLORS["dim_line"],
    text_color: str = COLORS["dim_text"],
    offset: float = 0.0,
    horizontal: bool = True
):
    """Add a dimension annotation line with label."""
    # Main line
    fig.add_shape(
        type="line",
        x0=x0, y0=y0, x1=x1, y1=y1,
        line=dict(color=color, width=1.5, dash="dot"),
    )

    # End ticks
    tick_size = 0.3
    if horizontal:
        for x in [x0, x1]:
            fig.add_shape(
                type="line",
                x0=x, y0=y0 - tick_size, x1=x, y1=y0 + tick_size,
                line=dict(color=color, width=1.5),
            )
    else:
        for y in [y0, y1]:
            fig.add_shape(
                type="line",
                x0=x0 - tick_size, y0=y, x1=x0 + tick_size, y1=y,
                line=dict(color=color, width=1.5),
            )

    # Label
    mid_x = (x0 + x1) / 2
    mid_y = (y0 + y1) / 2
    fig.add_annotation(
        x=mid_x, y=mid_y + offset,
        text=f"<b>{label}</b>",
        showarrow=False,
        font=dict(size=10, color=text_color, family="Inter, sans-serif"),
        bgcolor="rgba(255,255,255,0.85)",
        borderpad=2,
    )


def create_plan_view(
    dike: DikeInput,
    tanks: List[TankInput],
    clearances: List[ClearanceResult]
) -> go.Figure:
    """
    Create a top-down Plan View showing:
    - Dike boundary (rectangle)
    - Tanks (circles) with labels
    - Clearance dimension lines (dike-to-tank, tank-to-tank)
    - Violation warnings (red) for < 1.5m
    """
    fig = go.Figure()

    # ── Dike boundary ──
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=dike.L, y1=dike.W,
        line=dict(color=COLORS["dike_line"], width=3),
        fillcolor=COLORS["dike_fill"],
        layer="below",
    )

    # Dike label
    fig.add_annotation(
        x=dike.L / 2, y=-1.5,
        text=f"<b>Dike: {dike.L}m × {dike.W}m (H={dike.H_dike}m)</b>",
        showarrow=False,
        font=dict(size=12, color=COLORS["dike_line"], family="Inter, sans-serif"),
    )

    # ── Tanks ──
    for t in tanks:
        xs, ys = _circle_points(t.x, t.y, t.radius)

        # Tank circle fill
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            fill="toself",
            fillcolor=COLORS["tank_fill"],
            line=dict(color=COLORS["tank_line"], width=2),
            name=t.name,
            hovertemplate=(
                f"<b>{t.name}</b><br>"
                f"Ø{t.diameter}m × H{t.height}m<br>"
                f"V={t.volume:.1f} m³<br>"
                f"Position: ({t.x:.1f}, {t.y:.1f})"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

        # Tank label
        fig.add_annotation(
            x=t.x, y=t.y,
            text=f"<b>{t.name}</b><br>Ø{t.diameter}m",
            showarrow=False,
            font=dict(size=11, color=COLORS["tank_label"], family="Inter, sans-serif"),
            bgcolor="rgba(255,255,255,0.7)",
            borderpad=3,
        )

    # ── Dimension lines: Dike-to-Tank clearances ──
    for t in tanks:
        # Nearest wall distances
        d_left = t.x - t.radius
        d_right = dike.L - (t.x + t.radius)
        d_bottom = t.y - t.radius
        d_top = dike.W - (t.y + t.radius)

        # Show the minimum clearance dimension
        min_d = min(d_left, d_right, d_bottom, d_top)
        is_violation = min_d < 1.5
        color = COLORS["violation_line"] if is_violation else COLORS["dim_line"]
        text_color = COLORS["violation_text"] if is_violation else COLORS["dim_text"]
        label = f"{min_d:.2f}m" + (" ⚠" if is_violation else "")

        # Draw to nearest wall
        if min_d == d_left:
            _add_dimension_line(fig, 0, t.y, t.x - t.radius, t.y,
                                label, color, text_color, offset=0.8)
        elif min_d == d_right:
            _add_dimension_line(fig, t.x + t.radius, t.y, dike.L, t.y,
                                label, color, text_color, offset=0.8)
        elif min_d == d_bottom:
            _add_dimension_line(fig, t.x, 0, t.x, t.y - t.radius,
                                label, color, text_color, offset=0.0, horizontal=False)
        else:
            _add_dimension_line(fig, t.x, t.y + t.radius, t.x, dike.W,
                                label, color, text_color, offset=0.0, horizontal=False)

    # ── Dimension lines: Tank-to-Tank clearances ──
    for i in range(len(tanks)):
        for j in range(i + 1, len(tanks)):
            ta, tb = tanks[i], tanks[j]
            center_dist = math.sqrt((ta.x - tb.x) ** 2 + (ta.y - tb.y) ** 2)
            edge_dist = center_dist - ta.radius - tb.radius

            is_violation = edge_dist < 1.5
            color = COLORS["violation_line"] if is_violation else COLORS["dim_line"]
            text_color = COLORS["violation_text"] if is_violation else COLORS["dim_text"]
            label = f"{edge_dist:.2f}m" + (" ⚠" if is_violation else "")

            # Direction vector from ta to tb
            dx = tb.x - ta.x
            dy = tb.y - ta.y
            if center_dist > 0:
                ux, uy = dx / center_dist, dy / center_dist
            else:
                ux, uy = 1, 0

            # Points on tank edges along the connecting line
            x0 = ta.x + ux * ta.radius
            y0 = ta.y + uy * ta.radius
            x1 = tb.x - ux * tb.radius
            y1 = tb.y - uy * tb.radius

            is_horiz = abs(dx) > abs(dy)
            _add_dimension_line(fig, x0, y0, x1, y1,
                                label, color, text_color,
                                offset=0.8 if is_horiz else 0.0,
                                horizontal=is_horiz)

    # ── Layout ──
    margin = max(dike.L, dike.W) * 0.12
    fig.update_layout(
        title=dict(
            text="<b>📐 Plan View (평면도)</b>",
            font=dict(size=16, family="Inter, sans-serif", color="#2C3E50"),
            x=0.5,
        ),
        xaxis=dict(
            title="Length (m)",
            range=[-margin, dike.L + margin],
            scaleanchor="y",
            scaleratio=1,
            gridcolor=COLORS["grid"],
            zeroline=False,
            dtick=5,
        ),
        yaxis=dict(
            title="Width (m)",
            range=[-margin * 1.5, dike.W + margin],
            gridcolor=COLORS["grid"],
            zeroline=False,
            dtick=5,
        ),
        plot_bgcolor=COLORS["bg"],
        paper_bgcolor="white",
        height=550,
        margin=dict(l=60, r=40, t=60, b=60),
        font=dict(family="Inter, sans-serif"),
    )

    return fig


def create_section_view(
    dike: DikeInput,
    tanks: List[TankInput],
    slope_pct: float = 0.0
) -> go.Figure:
    """
    Create a Section/Elevation View showing:
    - Dike walls and floor (with optional slope)
    - Tank cross-sections with height comparison
    - Submerged zone highlighting
    - Height dimension annotations
    """
    fig = go.Figure()

    # Sort tanks by x position for section view
    sorted_tanks = sorted(tanks, key=lambda t: t.x)

    # ── Ground line ──
    ground_y = 0
    margin_x = max(dike.L * 0.08, 2)

    # ── Dike floor (with slope) ──
    if slope_pct > 0:
        floor_drop = dike.L * slope_pct / 100.0
        # Floor slopes from left (high) to right (low) toward sump
        floor_xs = [-margin_x, 0, dike.L, dike.L + margin_x]
        floor_ys = [ground_y, ground_y, ground_y - floor_drop, ground_y - floor_drop]

        # Slope fill (triangular loss zone)
        fig.add_trace(go.Scatter(
            x=[0, dike.L, dike.L, 0],
            y=[ground_y, ground_y - floor_drop, ground_y, ground_y],
            fill="toself",
            fillcolor=COLORS["slope_fill"],
            line=dict(width=0),
            name=f"Slope Loss ({slope_pct}%)",
            showlegend=True,
            hovertemplate="Slope volume loss zone<extra></extra>",
        ))

        # Sloped floor line
        fig.add_trace(go.Scatter(
            x=[0, dike.L],
            y=[ground_y, ground_y - floor_drop],
            mode="lines",
            line=dict(color=COLORS["ground_line"], width=2, dash="dash"),
            showlegend=False,
        ))
    else:
        floor_drop = 0

    # Ground surface
    fig.add_shape(
        type="line",
        x0=-margin_x, y0=ground_y, x1=dike.L + margin_x, y1=ground_y,
        line=dict(color=COLORS["ground_line"], width=2),
    )

    # ── Dike walls ──
    wall_thickness = max(dike.L * 0.015, 0.3)

    # Left wall
    fig.add_shape(
        type="rect",
        x0=-wall_thickness, y0=ground_y - floor_drop * 0.1,
        x1=0, y1=dike.H_dike,
        fillcolor=COLORS["dike_wall_fill"],
        line=dict(color=COLORS["dike_line"], width=2),
    )

    # Right wall
    fig.add_shape(
        type="rect",
        x0=dike.L, y0=ground_y - floor_drop,
        x1=dike.L + wall_thickness, y1=dike.H_dike,
        fillcolor=COLORS["dike_wall_fill"],
        line=dict(color=COLORS["dike_line"], width=2),
    )

    # Dike height dimension
    dim_x = -wall_thickness - 2.0
    _add_dimension_line(fig, dim_x, ground_y, dim_x, dike.H_dike,
                        f"H_dike={dike.H_dike}m",
                        COLORS["dike_line"], COLORS["dike_line"],
                        offset=0.0, horizontal=False)

    # Dike top line (dashed)
    fig.add_shape(
        type="line",
        x0=-wall_thickness, y0=dike.H_dike,
        x1=dike.L + wall_thickness, y1=dike.H_dike,
        line=dict(color=COLORS["dike_line"], width=1, dash="dash"),
    )

    # ── Tanks (cross-section rectangles) ──
    max_h = max((t.height for t in tanks), default=dike.H_dike)

    for t in sorted_tanks:
        # Tank rectangle (projected width = diameter)
        tank_x0 = t.x - t.radius
        tank_x1 = t.x + t.radius
        tank_y0 = ground_y
        tank_y1 = t.height

        # Full tank outline
        fig.add_shape(
            type="rect",
            x0=tank_x0, y0=tank_y0, x1=tank_x1, y1=tank_y1,
            fillcolor=COLORS["tank_fill"],
            line=dict(color=COLORS["tank_line"], width=2),
        )

        # Submerged zone (below dike height) - highlight
        sub_h = min(t.height, dike.H_dike)
        fig.add_shape(
            type="rect",
            x0=tank_x0, y0=tank_y0, x1=tank_x1, y1=sub_h,
            fillcolor=COLORS["submerged_fill"],
            line=dict(color="rgba(255,160,40,0.6)", width=1, dash="dot"),
        )

        # Tank label
        fig.add_annotation(
            x=t.x, y=tank_y1 + max_h * 0.04,
            text=f"<b>{t.name}</b><br>Ø{t.diameter}m",
            showarrow=False,
            font=dict(size=10, color=COLORS["tank_label"], family="Inter, sans-serif"),
            bgcolor="rgba(255,255,255,0.8)",
            borderpad=2,
        )

        # Tank height dimension (right side of tank)
        dim_tx = tank_x1 + 1.0
        _add_dimension_line(fig, dim_tx, ground_y, dim_tx, tank_y1,
                            f"H={t.height}m",
                            COLORS["tank_line"], COLORS["tank_label"],
                            offset=0.0, horizontal=False)

    # ── Legend entries ──
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        marker=dict(size=12, color=COLORS["submerged_fill"], symbol="square"),
        name="Submerged Zone (차감 영역)",
        showlegend=True,
    ))

    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        marker=dict(size=12, color=COLORS["dike_wall_fill"], symbol="square"),
        name=f"Dike Wall (H={dike.H_dike}m)",
        showlegend=True,
    ))

    # ── Layout ──
    y_max = max(max_h, dike.H_dike) * 1.3
    fig.update_layout(
        title=dict(
            text="<b>📏 Section View (단면도)</b>",
            font=dict(size=16, family="Inter, sans-serif", color="#2C3E50"),
            x=0.5,
        ),
        xaxis=dict(
            title="Position along Length (m)",
            range=[-margin_x - 3, dike.L + margin_x + 3],
            gridcolor=COLORS["grid"],
            zeroline=False,
            dtick=5,
        ),
        yaxis=dict(
            title="Height (m)",
            range=[ground_y - floor_drop - 1, y_max],
            gridcolor=COLORS["grid"],
            zeroline=False,
        ),
        plot_bgcolor=COLORS["bg"],
        paper_bgcolor="white",
        height=450,
        margin=dict(l=60, r=40, t=60, b=60),
        font=dict(family="Inter, sans-serif"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)",
            font=dict(size=10),
        ),
    )

    return fig


def create_result_chart(calc_result) -> go.Figure:
    """
    Create a bar chart comparing required volume vs effective volume.
    """
    dike_term = getattr(calc_result, 'dike_term', '방유제')
    factor_pct = int(getattr(calc_result, 'volume_factor', 1.0) * 100)

    categories = [
        f"{dike_term} 전체\n(V_dike)",
        "차감 합계\n(Deductions)",
        "유효용량\n(V_eff)",
        f"요구용량\n({factor_pct}% + Margin)",
    ]

    deductions_total = (
        calc_result.V_sub_tanks
        + calc_result.V_foundations
        + calc_result.V_piping
        + calc_result.V_slope
    )

    values = [
        calc_result.V_dike,
        deductions_total,
        calc_result.V_eff,
        calc_result.V_required_total,
    ]

    bar_colors = [
        "#4A90D9",     # dike total - blue
        "#E8833A",     # deductions - orange
        "#27AE60" if calc_result.is_pass else "#E53935",  # effective - green/red
        "#8E44AD",     # required - purple
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        marker=dict(
            color=bar_colors,
            line=dict(color="rgba(0,0,0,0.1)", width=1),
        ),
        text=[f"{v:,.1f} m³" for v in values],
        textposition="outside",
        textfont=dict(size=12, family="Inter, sans-serif", color="#2C3E50"),
        hovertemplate="%{x}<br><b>%{y:,.2f} m³</b><extra></extra>",
    ))

    # Pass/Fail annotation
    verdict = "✅ PASS (적합)" if calc_result.is_pass else "❌ FAIL (부적합)"
    verdict_color = "#27AE60" if calc_result.is_pass else "#E53935"

    fig.add_annotation(
        x=0.5, y=1.12,
        xref="paper", yref="paper",
        text=f"<b>{verdict}  |  여유율: {calc_result.margin_pct:+.1f}%</b>",
        showarrow=False,
        font=dict(size=16, color=verdict_color, family="Inter, sans-serif"),
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=verdict_color,
        borderwidth=2,
        borderpad=8,
    )

    fig.update_layout(
        title=dict(
            text="<b>📊 Volume Comparison</b>",
            font=dict(size=16, family="Inter, sans-serif", color="#2C3E50"),
            x=0.5,
        ),
        yaxis=dict(
            title="Volume (m³)",
            gridcolor=COLORS["grid"],
            zeroline=True,
            zerolinecolor=COLORS["grid"],
        ),
        xaxis=dict(tickfont=dict(size=11)),
        plot_bgcolor=COLORS["bg"],
        paper_bgcolor="white",
        height=450,
        margin=dict(l=60, r=40, t=90, b=60),
        font=dict(family="Inter, sans-serif"),
        showlegend=False,
    )

    return fig
