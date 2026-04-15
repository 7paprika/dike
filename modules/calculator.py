"""
Dike Volume Calculator — Core Calculation Engine
Based on KOSHA GUIDE D-8-2017 / 위험물안전관리법 / 화학물질관리법

Calculates effective dike volume, deductions, and compliance checks.
"""

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
#  Regulation Definitions
# ═══════════════════════════════════════════════════════════════
REGULATIONS: Dict[str, dict] = {
    "kosha": {
        "name": "산업안전보건법 (KOSHA GUIDE D-8-2017)",
        "short_name": "KOSHA GUIDE D-8-2017",
        "authority": "고용노동부",
        "target": "일반적인 위험물질",
        "volume_factor": 1.00,  # 최대 탱크 용량의 100%
        "description": "위험물질 누출방지를 위한 방유제 설치에 관한 기술지침",
        "dike_term": "방유제",
    },
    "fire_safety": {
        "name": "위험물안전관리법",
        "short_name": "위험물안전관리법",
        "authority": "소방청",
        "target": "제4류 위험물 (인화성 액체 등)",
        "volume_factor": 1.10,  # 최대 탱크 용량의 110%
        "description": "인화성이 없는 액체 위험물은 예외적으로 100% 적용 가능",
        "dike_term": "방유제",
    },
    "chemical": {
        "name": "화학물질관리법",
        "short_name": "화학물질관리법",
        "authority": "환경부",
        "target": "유해화학물질",
        "volume_factor": 1.10,  # 최대 탱크 용량의 110%
        "description": "법적 용어로 방유제 대신 '방류벽' 사용",
        "dike_term": "방류벽",
    },
}

# User-facing labels for selectbox
REGULATION_LABELS = {
    "kosha": "🏭 산업안전보건법 (KOSHA GUIDE) — 100%",
    "fire_safety": "🚒 위험물안전관리법 — 110%",
    "chemical": "🧪 화학물질관리법 — 110%",
}


@dataclass
class TankInput:
    """Individual tank specification."""
    name: str = "T-101"
    diameter: float = 10.0       # m
    height: float = 12.0         # m
    x: float = 0.0               # center X coordinate (m)
    y: float = 0.0               # center Y coordinate (m)
    V_foundation: float = 0.0    # foundation volume (m³)
    V_piping: float = 0.0        # piping/accessories volume (m³)

    @property
    def radius(self) -> float:
        return self.diameter / 2.0

    @property
    def volume(self) -> float:
        """Full tank volume (cylinder)."""
        return math.pi / 4.0 * self.diameter ** 2 * self.height

    def submerged_volume(self, h_dike: float) -> float:
        """Volume of tank below dike height."""
        h_sub = min(self.height, h_dike)
        return math.pi / 4.0 * self.diameter ** 2 * h_sub


@dataclass
class DikeInput:
    """Dike enclosure specification."""
    L: float = 30.0              # length (m)
    W: float = 20.0              # width (m)
    H_dike: float = 1.5          # height (m), valid: 0.5 ~ 3.0


@dataclass
class AdvancedInput:
    """Advanced correction inputs."""
    # Applicable regulation
    regulation_key: str = "kosha"  # "kosha" | "fire_safety" | "chemical"

    # Rainfall
    enable_rain: bool = False
    rainfall_mm: float = 0.0     # mm/hr (단일 시간 최대 강우량)

    # Fire water
    enable_fire: bool = False
    fire_flow_rate: float = 0.0  # m³/hr
    fire_duration: float = 0.0   # hr

    # Margin method: "max" or "sum"
    margin_method: str = "max"

    # Slope correction
    enable_slope: bool = False
    slope_pct: float = 0.0       # %


@dataclass
class ClearanceResult:
    """Clearance check result for a single pair."""
    item_a: str
    item_b: str
    distance: float              # m
    min_required: float = 1.5    # m (KOSHA GUIDE)
    is_pass: bool = True


@dataclass
class CalcResult:
    """Complete calculation result."""
    # Regulation
    regulation_key: str = "kosha"
    regulation_name: str = ""
    volume_factor: float = 1.0
    dike_term: str = "방유제"

    # Basic volumes
    V_dike: float = 0.0
    V_req: float = 0.0          # raw max tank volume
    V_req_factored: float = 0.0 # V_req × volume_factor
    largest_tank_name: str = ""

    # Deductions
    V_sub_tanks: float = 0.0
    V_foundations: float = 0.0
    V_piping: float = 0.0

    # Advanced corrections
    V_rain: float = 0.0
    V_fire: float = 0.0
    V_margin: float = 0.0
    margin_method: str = "max"
    V_slope: float = 0.0

    # Final
    V_eff: float = 0.0
    V_required_total: float = 0.0
    is_pass: bool = False
    margin_pct: float = 0.0

    # Clearances
    clearances: List[ClearanceResult] = field(default_factory=list)

    # Per-tank details
    tank_volumes: List[dict] = field(default_factory=list)


def auto_arrange_tanks(dike: DikeInput, tanks: List[TankInput]) -> List[TankInput]:
    """
    Automatically arrange tanks in a grid layout within the dike,
    ensuring minimum clearance from dike walls.
    Modifies tank x, y in-place and returns the list.
    """
    if not tanks:
        return tanks

    n = len(tanks)
    min_margin = 2.0  # minimum distance from dike wall to tank edge

    if n == 1:
        tanks[0].x = dike.L / 2.0
        tanks[0].y = dike.W / 2.0
        return tanks

    # Determine grid: try to fit in a single row first
    # Calculate available width after margins
    avail_L = dike.L - 2 * min_margin
    avail_W = dike.W - 2 * min_margin

    # Try single row (all tanks along L direction)
    total_diameter = sum(t.diameter for t in tanks)
    min_spacing = 2.0  # minimum gap between tanks
    total_needed = total_diameter + (n - 1) * min_spacing

    if total_needed <= avail_L:
        # Single row arrangement
        # Distribute tanks evenly along L
        spacing = (avail_L - total_diameter) / max(n - 1, 1) if n > 1 else 0
        current_x = min_margin + tanks[0].radius
        for t in tanks:
            t.x = current_x
            t.y = dike.W / 2.0
            current_x += t.diameter + spacing
    else:
        # Multi-row arrangement
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

        cell_w = avail_L / cols
        cell_h = avail_W / rows

        for i, t in enumerate(tanks):
            col = i % cols
            row = i // cols
            t.x = min_margin + cell_w * (col + 0.5)
            t.y = min_margin + cell_h * (row + 0.5)

    return tanks


def calc_clearances(dike: DikeInput, tanks: List[TankInput]) -> List[ClearanceResult]:
    """
    Calculate all clearance distances:
    - Each tank to each dike wall (4 walls)
    - Each tank pair
    """
    results = []

    for t in tanks:
        # Distance from tank edge to each dike wall
        d_left = t.x - t.radius
        d_right = dike.L - (t.x + t.radius)
        d_bottom = t.y - t.radius
        d_top = dike.W - (t.y + t.radius)

        min_d = min(d_left, d_right, d_bottom, d_top)
        results.append(ClearanceResult(
            item_a=t.name,
            item_b="Dike Wall (nearest)",
            distance=round(min_d, 3),
            is_pass=min_d >= 1.5
        ))

    # Tank-to-tank distances
    for i in range(len(tanks)):
        for j in range(i + 1, len(tanks)):
            ta, tb = tanks[i], tanks[j]
            center_dist = math.sqrt((ta.x - tb.x) ** 2 + (ta.y - tb.y) ** 2)
            edge_dist = center_dist - ta.radius - tb.radius
            results.append(ClearanceResult(
                item_a=ta.name,
                item_b=tb.name,
                distance=round(edge_dist, 3),
                is_pass=edge_dist >= 1.5
            ))

    return results


def calculate(
    dike: DikeInput,
    tanks: List[TankInput],
    advanced: Optional[AdvancedInput] = None
) -> CalcResult:
    """
    Main calculation function.
    Returns a CalcResult with all intermediate and final values.
    """
    if advanced is None:
        advanced = AdvancedInput()

    result = CalcResult()

    # ── Step 1: Basic dike volume ──
    result.V_dike = dike.L * dike.W * dike.H_dike

    # ── Step 2: Tank volumes & required capacity ──
    tank_vols = []
    for t in tanks:
        vol = t.volume
        tank_vols.append({
            "name": t.name,
            "diameter": t.diameter,
            "height": t.height,
            "volume": round(vol, 3),
            "submerged_volume": round(t.submerged_volume(dike.H_dike), 3),
            "V_foundation": t.V_foundation,
            "V_piping": t.V_piping,
        })
    result.tank_volumes = tank_vols

    # ── Regulation setup ──
    reg = REGULATIONS.get(advanced.regulation_key, REGULATIONS["kosha"])
    result.regulation_key = advanced.regulation_key
    result.regulation_name = reg["name"]
    result.volume_factor = reg["volume_factor"]
    result.dike_term = reg["dike_term"]

    if tank_vols:
        largest_idx = max(range(len(tank_vols)), key=lambda i: tank_vols[i]["volume"])
        result.V_req = tank_vols[largest_idx]["volume"]
        result.largest_tank_name = tank_vols[largest_idx]["name"]
    else:
        result.V_req = 0.0

    # Apply regulation volume factor
    result.V_req_factored = result.V_req * result.volume_factor

    # ── Step 3: Deductions ──
    # V_sub_tanks: submerged volume of all tanks EXCEPT the largest
    for i, t in enumerate(tanks):
        if tank_vols and tank_vols[i]["name"] == result.largest_tank_name:
            continue  # skip the largest tank
        result.V_sub_tanks += t.submerged_volume(dike.H_dike)

    # V_foundations and V_piping: ALL tanks
    result.V_foundations = sum(t.V_foundation for t in tanks)
    result.V_piping = sum(t.V_piping for t in tanks)

    # ── Step 4: Advanced corrections ──
    if advanced.enable_rain:
        result.V_rain = dike.L * dike.W * (advanced.rainfall_mm / 1000.0)

    if advanced.enable_fire:
        result.V_fire = advanced.fire_flow_rate * advanced.fire_duration

    # Margin
    result.margin_method = advanced.margin_method
    if advanced.margin_method == "max":
        result.V_margin = max(result.V_rain, result.V_fire)
    else:
        result.V_margin = result.V_rain + result.V_fire

    # Slope correction
    if advanced.enable_slope and advanced.slope_pct > 0:
        result.V_slope = 0.5 * (dike.L * dike.W) * (dike.L * advanced.slope_pct / 100.0)

    # ── Step 5: Effective volume & verdict ──
    result.V_eff = (
        result.V_dike
        - result.V_sub_tanks
        - result.V_foundations
        - result.V_piping
        - result.V_slope
    )

    result.V_required_total = result.V_req_factored + result.V_margin
    result.is_pass = result.V_eff >= result.V_required_total

    if result.V_required_total > 0:
        result.margin_pct = (
            (result.V_eff - result.V_required_total) / result.V_required_total * 100.0
        )
    else:
        result.margin_pct = 0.0

    # ── Step 6: Clearances ──
    result.clearances = calc_clearances(dike, tanks)

    return result
