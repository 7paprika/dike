"""
Dike Volume Calculator — URL-based State Save/Load

Encodes all input data into a compressed, URL-safe string.
No file upload needed — everything lives in the URL.
"""

import json
import zlib
import base64
from typing import Optional
import pandas as pd


def encode_state(state: dict) -> str:
    """Serialize state dict → compressed base64url string."""
    json_bytes = json.dumps(state, ensure_ascii=False).encode('utf-8')
    compressed = zlib.compress(json_bytes, level=9)
    return base64.urlsafe_b64encode(compressed).decode('ascii')


def decode_state(encoded: str) -> Optional[dict]:
    """Decode base64url string → state dict. Returns None on failure."""
    try:
        # Strip any whitespace or URL artifacts
        encoded = encoded.strip()
        # Add padding if needed
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += '=' * padding
        compressed = base64.urlsafe_b64decode(encoded)
        json_bytes = zlib.decompress(compressed)
        return json.loads(json_bytes.decode('utf-8'))
    except Exception:
        return None


def collect_state(
    project_info: dict,
    dike_params: dict,
    tanks_df: pd.DataFrame,
    advanced: dict,
    substance_type: str = "liquid",
    tank_config: str = "single"
) -> dict:
    """
    Collect all current input values into a single serializable dict.

    Args:
        project_info: {project_name, doc_no, engineer_name}
        dike_params: {L, W, H_dike}
        tanks_df: DataFrame with tank specs
        advanced: {enable_rain, rainfall_mm, enable_fire, fire_flow_rate,
                   fire_duration, margin_method, enable_slope, slope_pct}
        substance_type: "liquid" or "gas"
        tank_config: "single" or "multi"
    """
    return {
        "version": 1,
        "project": project_info,
        "substance_type": substance_type,
        "tank_config": tank_config,
        "dike": dike_params,
        "tanks": tanks_df.to_dict(orient="records"),
        "advanced": advanced
    }


def restore_state(state: dict) -> dict:
    """
    Parse a loaded state dict and return structured data ready for UI restoration.
    Returns dict with keys: project, substance_type, tank_config, dike, tanks_df, advanced
    """
    tanks_df = pd.DataFrame(state.get("tanks", []))
    return {
        "project": state.get("project", {}),
        "substance_type": state.get("substance_type", "liquid"),
        "tank_config": state.get("tank_config", "single"),
        "dike": state.get("dike", {}),
        "tanks_df": tanks_df,
        "advanced": state.get("advanced", {})
    }


def build_save_url(base_url: str, state: dict) -> str:
    """Build a full URL with encoded state as query parameter."""
    encoded = encode_state(state)
    # Clean the base URL
    base_url = base_url.split('?')[0]
    return f"{base_url}?data={encoded}"


def estimate_url_length(state: dict) -> int:
    """Estimate the length of the encoded data parameter."""
    encoded = encode_state(state)
    return len(encoded)
