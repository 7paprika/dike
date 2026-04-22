"""
Dike Volume Calculator — Main Streamlit Application
Based on KOSHA GUIDE D-8-2017

Run: streamlit run app.py
"""

import os
import math

import streamlit as st
import pandas as pd

from modules.calculator import (
    DikeInput, TankInput, AdvancedInput, calculate, auto_arrange_tanks,
    REGULATIONS, REGULATION_LABELS
)
from modules.visualization import (
    create_plan_view, create_section_view, create_result_chart
)
from modules.state_manager import (
    encode_state, decode_state, collect_state, restore_state,
    estimate_url_length
)
from modules.report_gen import generate_report


# ═══════════════════════════════════════════════════════════════
#  Page Config
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Dike Volume Calculator",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  Session State Initialization
# ═══════════════════════════════════════════════════════════════
def init_session():
    """Initialize default session state."""
    defaults = {
        "project_name": "",
        "doc_no": "",
        "engineer_name": "",
        "substance_type": "액체 (Liquid)",
        "tank_config": "단일 탱크",
        "regulation_key": "kosha",
        "dike_L": 30.0,
        "dike_W": 20.0,
        "dike_H": 1.5,
        "tanks_df": pd.DataFrame([
            {"name": "T-101", "diameter": 10.0, "height": 12.0,
             "x": 0.0, "y": 0.0, "V_foundation": 5.0, "V_piping": 1.0}
        ]),
        "enable_rain": False,
        "rainfall_mm": 50.0,
        "enable_fire": False,
        "fire_flow_rate": 0.0,
        "fire_duration": 0.0,
        "margin_method": "MAX (더 큰 값)",
        "enable_slope": False,
        "slope_pct": 1.0,
        "state_loaded": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def load_from_url():
    """Check URL query params for saved state and restore."""
    params = st.query_params
    if "data" in params and not st.session_state.get("state_loaded"):
        encoded = params["data"]
        state = decode_state(encoded)
        if state:
            restored = restore_state(state)
            # Project info
            proj = restored["project"]
            st.session_state["project_name"] = proj.get("project_name", "")
            st.session_state["doc_no"] = proj.get("doc_no", "")
            st.session_state["engineer_name"] = proj.get("engineer_name", "")
            st.session_state["substance_type"] = restored.get("substance_type", "액체 (Liquid)")
            st.session_state["tank_config"] = restored.get("tank_config", "단일 탱크")
            # Dike
            dike = restored["dike"]
            st.session_state["dike_L"] = dike.get("L", 30.0)
            st.session_state["dike_W"] = dike.get("W", 20.0)
            st.session_state["dike_H"] = dike.get("H_dike", 1.5)
            # Tanks
            if not restored["tanks_df"].empty:
                st.session_state["tanks_df"] = restored["tanks_df"]
            # Advanced
            adv = restored["advanced"]
            st.session_state["enable_rain"] = adv.get("enable_rain", False)
            st.session_state["rainfall_mm"] = adv.get("rainfall_mm", 50.0)
            st.session_state["enable_fire"] = adv.get("enable_fire", False)
            st.session_state["fire_flow_rate"] = adv.get("fire_flow_rate", 0.0)
            st.session_state["fire_duration"] = adv.get("fire_duration", 0.0)
            st.session_state["margin_method"] = adv.get("margin_method", "MAX (더 큰 값)")
            st.session_state["enable_slope"] = adv.get("enable_slope", False)
            st.session_state["slope_pct"] = adv.get("slope_pct", 1.0)
            st.session_state["state_loaded"] = True
            st.toast("✅ 저장된 데이터를 불러왔습니다!", icon="📂")


init_session()
load_from_url()


# ═══════════════════════════════════════════════════════════════
#  Sidebar
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🛢️ Dike Calculator")
    st.markdown("---")

    # Project Info
    st.markdown("### 📋 프로젝트 정보")
    project_name = st.text_input(
        "Project Name",
        value=st.session_state["project_name"],
        key="inp_project_name",
        placeholder="예: ABC Chemical Plant"
    )
    doc_no = st.text_input(
        "Document No.",
        value=st.session_state["doc_no"],
        key="inp_doc_no",
        placeholder="예: CAL-DIKE-001"
    )
    engineer_name = st.text_input(
        "Engineer Name",
        value=st.session_state["engineer_name"],
        key="inp_engineer_name",
        placeholder="예: 홍길동"
    )

    st.markdown("---")

    # Applicable Regulation
    st.markdown("### 📜 적용 법규")
    reg_labels = list(REGULATION_LABELS.values())
    reg_keys = list(REGULATION_LABELS.keys())
    current_reg_key = st.session_state.get("regulation_key", "kosha")
    current_reg_idx = reg_keys.index(current_reg_key) if current_reg_key in reg_keys else 0

    selected_reg_label = st.selectbox(
        "법규 선택",
        reg_labels,
        index=current_reg_idx,
        key="inp_regulation",
    )
    selected_reg_key = reg_keys[reg_labels.index(selected_reg_label)]
    st.session_state["regulation_key"] = selected_reg_key

    # Show regulation details
    reg_info = REGULATIONS[selected_reg_key]
    factor_pct = int(reg_info['volume_factor'] * 100)
    st.markdown(
        f'<div class="info-box">'
        f'<strong>소관 부처:</strong> {reg_info["authority"]}<br>'
        f'<strong>대상 물질:</strong> {reg_info["target"]}<br>'
        f'<strong>요구 기준:</strong> 최대 탱크 용량의 <strong>{factor_pct}%</strong> 이상<br>'
        f'<strong>용어:</strong> {reg_info["dike_term"]}'
        f'</div>',
        unsafe_allow_html=True
    )
    if reg_info.get("description"):
        st.caption(f"ℹ️ {reg_info['description']}")

    st.markdown("---")

    # Substance Type
    st.markdown("### ⚗️ 저장 물질 특성")
    substance_type = st.selectbox(
        "물질 유형",
        ["액체 (Liquid)", "가스 (Gas - 액화저장)"],
        index=0 if st.session_state["substance_type"] == "액체 (Liquid)" else 1,
        key="inp_substance_type"
    )

    if "가스" in substance_type:
        st.markdown(
            '<div class="warning-box">'
            '⚠️ <strong>경고:</strong> 가스 액화 저장 시 방유제 단면적을 최소화해야 합니다. '
            '증발 가스 확산을 억제하기 위해 방유제 면적을 최소로 설계하십시오.'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # Tank Configuration — simplified info display
    st.markdown("### 🏗️ 탱크 구성")
    n_current = len(st.session_state.get("tanks_df", pd.DataFrame()))
    tank_config = "단일 탱크" if n_current <= 1 else f"다중 탱크 ({n_current}기)"
    st.markdown(
        f'<div class="tank-count-badge">🛢️ 현재 탱크: <strong>{n_current}기</strong></div>',
        unsafe_allow_html=True
    )
    st.caption("탱크 추가/삭제는 Step 1 탭에서 가능합니다.")

    st.markdown("---")

    # Save / Load
    with st.expander("💾 저장 / 📂 불러오기", expanded=False):
        st.markdown(
            '<div class="info-box">'
            'URL 링크를 통해 입력 데이터를 저장하고 불러올 수 있습니다. '
            '파일 업로드가 필요 없습니다.'
            '</div>',
            unsafe_allow_html=True
        )
        st.markdown("")

        if st.button("🔗 저장 링크 생성", width="stretch"):
            state = collect_state(
                project_info={
                    "project_name": project_name,
                    "doc_no": doc_no,
                    "engineer_name": engineer_name,
                },
                dike_params={
                    "L": st.session_state.get("dike_L", 30.0),
                    "W": st.session_state.get("dike_W", 20.0),
                    "H_dike": st.session_state.get("dike_H", 1.5),
                },
                tanks_df=st.session_state.get("tanks_df", pd.DataFrame()),
                advanced={
                    "enable_rain": st.session_state.get("enable_rain", False),
                    "rainfall_mm": st.session_state.get("rainfall_mm", 50.0),
                    "enable_fire": st.session_state.get("enable_fire", False),
                    "fire_flow_rate": st.session_state.get("fire_flow_rate", 0.0),
                    "fire_duration": st.session_state.get("fire_duration", 0.0),
                    "margin_method": st.session_state.get("margin_method", "MAX (더 큰 값)"),
                    "enable_slope": st.session_state.get("enable_slope", False),
                    "slope_pct": st.session_state.get("slope_pct", 1.0),
                },
                substance_type=substance_type,
                tank_config=tank_config,
            )
            encoded = encode_state(state)
            url_len = len(encoded)

            if url_len > 7000:
                st.warning(f"⚠️ 데이터 크기({url_len}자)가 URL 제한에 근접합니다.")

            st.code(encoded, language=None)
            st.caption("↑ 위 코드를 복사하여 저장하세요.")

        st.markdown("")
        load_code = st.text_area(
            "📂 저장 코드 붙여넣기",
            height=80,
            placeholder="저장된 코드를 여기에 붙여넣으세요...",
            key="load_input",
        )
        if st.button("불러오기", width="stretch"):
            if load_code.strip():
                state = decode_state(load_code.strip())
                if state:
                    restored = restore_state(state)
                    proj = restored["project"]
                    st.session_state["project_name"] = proj.get("project_name", "")
                    st.session_state["doc_no"] = proj.get("doc_no", "")
                    st.session_state["engineer_name"] = proj.get("engineer_name", "")
                    st.session_state["substance_type"] = restored.get("substance_type", "액체 (Liquid)")
                    st.session_state["tank_config"] = restored.get("tank_config", "단일 탱크")
                    dike = restored["dike"]
                    st.session_state["dike_L"] = dike.get("L", 30.0)
                    st.session_state["dike_W"] = dike.get("W", 20.0)
                    st.session_state["dike_H"] = dike.get("H_dike", 1.5)
                    if not restored["tanks_df"].empty:
                        st.session_state["tanks_df"] = restored["tanks_df"]
                    adv = restored["advanced"]
                    for k, v in adv.items():
                        st.session_state[k] = v
                    st.toast("✅ 데이터를 성공적으로 불러왔습니다!", icon="📂")
                    st.rerun()
                else:
                    st.error("❌ 유효하지 않은 코드입니다.")
            else:
                st.warning("저장 코드를 입력해 주세요.")


# ═══════════════════════════════════════════════════════════════
#  Main Area
# ═══════════════════════════════════════════════════════════════

# Title
st.markdown(
    '<div class="main-title">'
    '<h1>🛢️ Dike Volume Calculator</h1>'
    '<div class="subtitle">KOSHA GUIDE D-8-2017 기반 방유제 유효용량 계산기</div>'
    '</div>',
    unsafe_allow_html=True
)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📐 Step 1: 기본 제원",
    "🗺️ Step 2: 배치 도식화",
    "⚙️ Step 3: 상세 보정",
    "📊 Step 4: 결과 & Report",
])


# ─── TAB 1: Basic Parameters ───
with tab1:
    st.markdown("### 방유제 제원 (Dike Dimensions)")

    col1, col2, col3 = st.columns(3)
    with col1:
        dike_L = st.number_input(
            "가로 Length, L (m)",
            min_value=1.0, max_value=500.0,
            value=st.session_state["dike_L"],
            step=0.5,
            key="inp_dike_L",
            help="방유제 내부 가로 길이"
        )
    with col2:
        dike_W = st.number_input(
            "세로 Width, W (m)",
            min_value=1.0, max_value=500.0,
            value=st.session_state["dike_W"],
            step=0.5,
            key="inp_dike_W",
            help="방유제 내부 세로 길이"
        )
    with col3:
        dike_H = st.number_input(
            "높이 Height, H (m)",
            min_value=0.5, max_value=3.0,
            value=st.session_state["dike_H"],
            step=0.1,
            key="inp_dike_H",
            help="KOSHA GUIDE: 0.5m ≤ H ≤ 3.0m"
        )

    # Validate dike height
    if dike_H < 0.5 or dike_H > 3.0:
        st.error("⚠️ 방유제 높이는 0.5m ~ 3.0m 범위여야 합니다 (KOSHA GUIDE D-8-2017).")

    # Update session
    st.session_state["dike_L"] = dike_L
    st.session_state["dike_W"] = dike_W
    st.session_state["dike_H"] = dike_H

    st.markdown("---")
    st.markdown("### 탱크 제원 (Tank Specifications)")
    st.markdown(
        '<div class="info-box">'
        '💡 <strong>X, Y 좌표</strong>: 탱크 중심 위치 (방유제 좌하단 = 원점). '
        '0으로 두면 자동 배치됩니다.'
        '</div>',
        unsafe_allow_html=True
    )

    # ── Tank Add/Remove Buttons ──
    st.markdown("")
    current_df = st.session_state["tanks_df"]
    n_tanks = len(current_df)

    # Tank count display + buttons
    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
    with btn_col1:
        st.markdown(
            f'<div class="tank-count-badge">🛢️ 현재 탱크: <strong>{n_tanks}기</strong></div>',
            unsafe_allow_html=True
        )
    with btn_col2:
        add_tank = st.button("➕ 탱크 추가", key="btn_add_tank", width="stretch", type="primary")
    with btn_col3:
        remove_tank = st.button("➖ 탱크 삭제", key="btn_remove_tank", width="stretch",
                                 disabled=(n_tanks <= 1))

    # Handle add
    if add_tank:
        next_idx = n_tanks
        new_row = pd.DataFrame([{
            "name": f"T-{101 + next_idx}",
            "diameter": 10.0,
            "height": 12.0,
            "x": 0.0, "y": 0.0,
            "V_foundation": 0.0,
            "V_piping": 0.0,
        }])
        st.session_state["tanks_df"] = pd.concat(
            [current_df, new_row], ignore_index=True
        )
        st.rerun()

    # Handle remove
    if remove_tank and n_tanks > 1:
        st.session_state["tanks_df"] = current_df.iloc[:-1].reset_index(drop=True)
        st.rerun()

    # Refresh after potential changes
    current_df = st.session_state["tanks_df"]

    # Data editor
    edited_df = st.data_editor(
        current_df,
        num_rows="fixed",
        width="stretch",
        column_config={
            "name": st.column_config.TextColumn("탱크 ID", width="small"),
            "diameter": st.column_config.NumberColumn("직경 Ø (m)", min_value=0.1, step=0.1, format="%.1f"),
            "height": st.column_config.NumberColumn("높이 H (m)", min_value=0.1, step=0.1, format="%.1f"),
            "x": st.column_config.NumberColumn("X 위치 (m)", min_value=0.0, step=0.5, format="%.1f"),
            "y": st.column_config.NumberColumn("Y 위치 (m)", min_value=0.0, step=0.5, format="%.1f"),
            "V_foundation": st.column_config.NumberColumn("기초체적 (m³)", min_value=0.0, step=0.1, format="%.2f"),
            "V_piping": st.column_config.NumberColumn("부속설비 (m³)", min_value=0.0, step=0.1, format="%.2f"),
        },
        key="tank_editor",
    )
    st.session_state["tanks_df"] = edited_df

    # Show tank volumes preview
    if not edited_df.empty:
        st.markdown("#### 탱크 체적 미리보기")
        preview_data = []
        for _, row in edited_df.iterrows():
            vol = math.pi / 4 * row["diameter"] ** 2 * row["height"]
            preview_data.append({
                "탱크 ID": row["name"],
                "직경 (m)": row["diameter"],
                "높이 (m)": row["height"],
                "체적 (m³)": f"{vol:,.2f}",
            })
        st.dataframe(
            pd.DataFrame(preview_data),
            width="stretch",
            hide_index=True
        )


# ─── Helper: Build calculation inputs ───
def build_inputs():
    """Build DikeInput, TankInputs, AdvancedInput from session state."""
    dike = DikeInput(
        L=st.session_state["dike_L"],
        W=st.session_state["dike_W"],
        H_dike=st.session_state["dike_H"],
    )

    tanks = []
    df = st.session_state["tanks_df"]
    for _, row in df.iterrows():
        tanks.append(TankInput(
            name=str(row.get("name", "T-?")),
            diameter=float(row.get("diameter", 10.0)),
            height=float(row.get("height", 12.0)),
            x=float(row.get("x", 0.0)),
            y=float(row.get("y", 0.0)),
            V_foundation=float(row.get("V_foundation", 0.0)),
            V_piping=float(row.get("V_piping", 0.0)),
        ))

    # Auto-arrange if positions are all zero
    all_zero = all(t.x == 0 and t.y == 0 for t in tanks)
    if all_zero and tanks:
        tanks = auto_arrange_tanks(dike, tanks)

    adv_method = st.session_state.get("margin_method", "MAX (더 큰 값)")
    method = "max" if "MAX" in adv_method else "sum"

    advanced = AdvancedInput(
        regulation_key=st.session_state.get("regulation_key", "kosha"),
        enable_rain=st.session_state.get("enable_rain", False),
        rainfall_mm=st.session_state.get("rainfall_mm", 0.0),
        enable_fire=st.session_state.get("enable_fire", False),
        fire_flow_rate=st.session_state.get("fire_flow_rate", 0.0),
        fire_duration=st.session_state.get("fire_duration", 0.0),
        margin_method=method,
        enable_slope=st.session_state.get("enable_slope", False),
        slope_pct=st.session_state.get("slope_pct", 0.0),
    )

    return dike, tanks, advanced


# ─── TAB 2: Layout Visualization ───
with tab2:
    st.markdown("### 배치 도식화")
    st.markdown(
        '<div class="info-box">'
        '💡 Step 1에서 입력한 데이터가 실시간 반영됩니다. '
        'X, Y 좌표가 0이면 자동 배치됩니다.'
        '</div>',
        unsafe_allow_html=True
    )

    dike_viz, tanks_viz, adv_viz = build_inputs()
    result_viz = calculate(dike_viz, tanks_viz, adv_viz)

    # Plan View
    plan_fig = create_plan_view(dike_viz, tanks_viz, result_viz.clearances)
    st.plotly_chart(plan_fig, width="stretch", key="plan_view")

    # Section View
    slope_for_viz = adv_viz.slope_pct if adv_viz.enable_slope else 0.0
    section_fig = create_section_view(dike_viz, tanks_viz, slope_for_viz, result_viz.largest_tank_name)
    st.plotly_chart(section_fig, width="stretch", key="section_view")

    # Clearance table
    if result_viz.clearances:
        st.markdown("### 이격거리 검증 결과")
        cl_data = []
        for c in result_viz.clearances:
            status = "✅ PASS" if c.is_pass else "❌ FAIL"
            cl_data.append({
                "항목 A": c.item_a,
                "항목 B": c.item_b,
                "이격거리 (m)": f"{c.distance:.3f}",
                "최소 기준 (m)": f"{c.min_required:.1f}",
                "판정": status,
            })
        st.dataframe(
            pd.DataFrame(cl_data),
            width="stretch",
            hide_index=True,
        )

        # Violation warnings
        violations = [c for c in result_viz.clearances if not c.is_pass]
        if violations:
            st.markdown(
                '<div class="warning-box">'
                '⚠️ <strong>이격거리 기준 위반이 감지되었습니다!</strong><br>'
                '방유제 내면과 탱크 외면 사이 최소 1.5m를 유지해야 합니다 '
                '(KOSHA GUIDE D-8-2017).'
                '</div>',
                unsafe_allow_html=True
            )


# ─── TAB 3: Advanced Options ───
with tab3:
    st.markdown("### 상세 설계 보정 (Advanced Options)")

    # ── Rainfall / Fire water ──
    st.markdown("#### 🌧️ 우수량 / 소방수 여유 (Freeboard Margin)")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="adv-toggle">', unsafe_allow_html=True)
        enable_rain = st.toggle("우수량 고려", value=st.session_state["enable_rain"], key="tgl_rain")
        st.session_state["enable_rain"] = enable_rain

        if enable_rain:
            rainfall_mm = st.number_input(
                "최대 강우량 (mm/hr)",
                min_value=0.0, max_value=500.0,
                value=st.session_state["rainfall_mm"],
                step=5.0, key="inp_rain",
            )
            st.session_state["rainfall_mm"] = rainfall_mm

            # Preview
            v_rain = st.session_state["dike_L"] * st.session_state["dike_W"] * rainfall_mm / 1000
            st.info(f"V_rain = {st.session_state['dike_L']} × {st.session_state['dike_W']} × {rainfall_mm}/1000 = **{v_rain:.2f} m³**")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="adv-toggle">', unsafe_allow_html=True)
        enable_fire = st.toggle("소방수 고려", value=st.session_state["enable_fire"], key="tgl_fire")
        st.session_state["enable_fire"] = enable_fire

        if enable_fire:
            fire_flow = st.number_input(
                "소방수 방사량 (m³/hr)",
                min_value=0.0, max_value=1000.0,
                value=st.session_state["fire_flow_rate"],
                step=1.0, key="inp_fire_flow",
            )
            fire_dur = st.number_input(
                "방사 시간 (hr)",
                min_value=0.0, max_value=24.0,
                value=st.session_state["fire_duration"],
                step=0.5, key="inp_fire_dur",
            )
            st.session_state["fire_flow_rate"] = fire_flow
            st.session_state["fire_duration"] = fire_dur

            v_fire = fire_flow * fire_dur
            st.info(f"V_fire = {fire_flow} × {fire_dur} = **{v_fire:.2f} m³**")
        st.markdown('</div>', unsafe_allow_html=True)

    # Margin method
    if enable_rain or enable_fire:
        margin_method = st.radio(
            "적용 방식",
            ["MAX (더 큰 값)", "SUM (합산)"],
            index=0 if "MAX" in st.session_state.get("margin_method", "MAX") else 1,
            key="inp_margin_method",
            horizontal=True,
            help="MAX: 우수량과 소방수 중 큰 값 적용 / SUM: 두 값 합산"
        )
        st.session_state["margin_method"] = margin_method

    st.markdown("---")

    # ── Slope Correction ──
    st.markdown("#### 📐 경사도 체적 보정 (Slope Correction)")
    st.markdown('<div class="adv-toggle">', unsafe_allow_html=True)

    enable_slope = st.toggle(
        "바닥 경사도 적용",
        value=st.session_state["enable_slope"],
        key="tgl_slope",
        help="집수조(Sump) 방향 1% 이상 경사 적용"
    )
    st.session_state["enable_slope"] = enable_slope

    if enable_slope:
        slope_pct = st.number_input(
            "경사면 구배 (%)",
            min_value=0.1, max_value=10.0,
            value=st.session_state["slope_pct"],
            step=0.1, key="inp_slope",
        )
        st.session_state["slope_pct"] = slope_pct

        v_slope = 0.5 * st.session_state["dike_L"] * st.session_state["dike_W"] * (
            st.session_state["dike_L"] * slope_pct / 100
        )
        st.info(
            f"V_slope = 0.5 × {st.session_state['dike_L']} × {st.session_state['dike_W']} × "
            f"({st.session_state['dike_L']} × {slope_pct}/100) = **{v_slope:.2f} m³**"
        )
        st.caption("※ 1방향 단순 경사(삼각형 단면) 가정")

    st.markdown('</div>', unsafe_allow_html=True)


# ─── TAB 4: Results & Report ───
with tab4:
    st.markdown("### 계산 결과")

    # Run full calculation
    dike_calc, tanks_calc, adv_calc = build_inputs()
    result = calculate(dike_calc, tanks_calc, adv_calc)

    # ── Applied Regulation Badge ──
    reg_info = REGULATIONS.get(result.regulation_key, REGULATIONS["kosha"])
    factor_pct = int(result.volume_factor * 100)
    st.markdown(
        f'<div class="info-box">'
        f'📜 <strong>적용 법규:</strong> {result.regulation_name} '
        f'| <strong>요구 기준:</strong> 최대 탱크 용량 × {factor_pct}% '
        f'| <strong>용어:</strong> {result.dike_term}'
        f'</div>',
        unsafe_allow_html=True
    )
    st.markdown("")

    # ── Result Summary Cards ──
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)

    with col_r1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="mc-label">{result.dike_term} 전체 체적</div>'
            f'<div class="mc-value">{result.V_dike:,.1f} <span class="mc-unit">m³</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col_r2:
        ded = result.V_sub_tanks + result.V_foundations + result.V_piping + result.V_slope
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="mc-label">차감 합계</div>'
            f'<div class="mc-value">{ded:,.1f} <span class="mc-unit">m³</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col_r3:
        card_class = "pass" if result.is_pass else "fail"
        st.markdown(
            f'<div class="metric-card {card_class}">'
            f'<div class="mc-label">유효용량 (V_eff)</div>'
            f'<div class="mc-value">{result.V_eff:,.1f} <span class="mc-unit">m³</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col_r4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="mc-label">요구용량 ({factor_pct}% + Margin)</div>'
            f'<div class="mc-value">{result.V_required_total:,.1f} <span class="mc-unit">m³</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("")

    # ── Verdict ──
    if result.is_pass:
        st.markdown(
            f'<div class="verdict-pass">'
            f'✅ PASS (적합)  —  여유율: {result.margin_pct:+.1f}%'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="verdict-fail">'
            f'❌ FAIL (부적합)  —  여유율: {result.margin_pct:+.1f}%'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("")

    # ── Bar Chart ──
    result_chart = create_result_chart(result)
    st.plotly_chart(result_chart, width="stretch", key="result_chart")

    # ── Detailed Breakdown ──
    with st.expander("📋 상세 계산 내역", expanded=False):
        breakdown = {
            "항목": [
                f"V_dike ({result.dike_term} 전체)",
                f"V_req (최대 탱크: {result.largest_tank_name})",
                f"V_req × {factor_pct}% (법적 요구용량)",
                "V_sub_tanks (기타 탱크 침수부)",
                "V_foundations (기초 합계)",
                "V_piping (부속설비 합계)",
                "V_rain (우수량)",
                "V_fire (소방수)",
                f"V_margin ({result.margin_method.upper()})",
                "V_slope (경사 손실)",
                "V_eff (유효용량)",
                "V_required (요구 합계)",
            ],
            "체적 (m³)": [
                f"{result.V_dike:,.2f}",
                f"{result.V_req:,.2f}",
                f"{result.V_req_factored:,.2f}",
                f"{result.V_sub_tanks:,.2f}",
                f"{result.V_foundations:,.2f}",
                f"{result.V_piping:,.2f}",
                f"{result.V_rain:,.2f}",
                f"{result.V_fire:,.2f}",
                f"{result.V_margin:,.2f}",
                f"{result.V_slope:,.2f}",
                f"{result.V_eff:,.2f}",
                f"{result.V_required_total:,.2f}",
            ],
        }
        st.dataframe(pd.DataFrame(breakdown), width="stretch", hide_index=True)

    st.markdown("---")

    # ── HTML Report Download ──
    st.markdown("### 📥 Calculation Sheet 다운로드")

    if st.button("📄 HTML Report 생성", width="stretch", type="primary"):
        with st.spinner("리포트 생성 중..."):
            # Build figures for report
            plan_fig_r = create_plan_view(dike_calc, tanks_calc, result.clearances)
            slope_r = adv_calc.slope_pct if adv_calc.enable_slope else 0.0
            section_fig_r = create_section_view(dike_calc, tanks_calc, slope_r, result.largest_tank_name)
            result_fig_r = create_result_chart(result)

            html_report = generate_report(
                project_info={
                    "project_name": project_name,
                    "doc_no": doc_no,
                    "engineer_name": engineer_name,
                },
                dike_params={
                    "L": dike_calc.L,
                    "W": dike_calc.W,
                    "H_dike": dike_calc.H_dike,
                },
                tanks_df=st.session_state["tanks_df"],
                calc_result=result,
                advanced={
                    "enable_rain": adv_calc.enable_rain,
                    "rainfall_mm": adv_calc.rainfall_mm,
                    "enable_fire": adv_calc.enable_fire,
                    "fire_flow_rate": adv_calc.fire_flow_rate,
                    "fire_duration": adv_calc.fire_duration,
                    "margin_method": result.margin_method,
                    "enable_slope": adv_calc.enable_slope,
                    "slope_pct": adv_calc.slope_pct,
                },
                plan_view_fig=plan_fig_r,
                section_view_fig=section_fig_r,
                result_chart_fig=result_fig_r,
            )

            st.download_button(
                label="⬇️ HTML Calculation Sheet 다운로드",
                data=html_report,
                file_name=f"Dike_Calc_{doc_no or 'Report'}.html",
                mime="text/html",
                width="stretch",
            )

        st.success("✅ 리포트가 생성되었습니다. 위 버튼을 클릭하여 다운로드하세요.")
