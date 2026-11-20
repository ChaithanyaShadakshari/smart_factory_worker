"""
agent.py – Gemini-powered efficiency analysis agent.
Uses google-generativeai (NOT anthropic).
"""
import json
import os
import re
from pathlib import Path

import google.generativeai as genai

from database import get_connection, get_session_metrics

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _get_model() -> genai.GenerativeModel:
    """Configure Gemini and return the model instance."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set.\n"
            "Windows : set GEMINI_API_KEY=your_key_here\n"
            "Linux/Mac: export GEMINI_API_KEY=your_key_here"
        )
    genai.configure(api_key=api_key)
    # Use gemini-1.5-flash as it has more generous free-tier limits globally
    return genai.GenerativeModel("gemini-1.5-flash")


def _status(score: float) -> str:
    if score < 60:
        return "RED"
    if score <= 75:
        return "AMBER"
    return "GREEN"


def _build_prompt(workers_data: list[dict]) -> str:
    n = len(workers_data)
    data_json = json.dumps(workers_data, indent=2)

    system_context = (
        "You are a factory efficiency analyst. "
        "Analyze worker performance data and return insights as JSON."
    )

    user_prompt = f"""{system_context}

Here is efficiency data for {n} workers. For each worker, write ONE concise sentence \
(max 20 words) explaining performance. Mention active_ratio and burst count.

Data:
{data_json}

Return ONLY a valid JSON array, no markdown, no explanation, no backticks:
[
  {{
    "worker_id": "W042",
    "score": 54.2,
    "rank": 3,
    "status": "RED",
    "narrative": "40% active ratio with low burst frequency suggests end-of-line bottleneck pattern."
  }}
]"""
    return user_prompt


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def run_agent(session_id: str) -> list[dict]:
    """
    Run the Gemini agent for a given session and return enriched worker dicts.

    Steps:
      1. Load metrics from SQLite
      2. Rank workers, compute status
      3. Call Gemini API
      4. Parse response JSON
      5. Save output/report_payload.json
      6. Return enriched list
    """
    model = _get_model()

    conn = get_connection()
    rows = get_session_metrics(conn, session_id)
    conn.close()

    if not rows:
        raise ValueError(f"No data found for session_id='{session_id}'")

    # Compute division averages and per-worker rank
    scores = [r["efficiency_score"] for r in rows]
    avg_score = sum(scores) / len(scores)

    # Sort descending by score; rank 1 = best
    sorted_rows = sorted(rows, key=lambda r: r["efficiency_score"], reverse=True)
    for rank_idx, row in enumerate(sorted_rows, start=1):
        row["rank"] = rank_idx
        row["status"] = _status(row["efficiency_score"])
        row["division_avg_score"] = round(avg_score, 2)

    prompt = _build_prompt(sorted_rows)

    try:
        response = model.generate_content(prompt)
        raw = response.text
        cleaned = _strip_markdown_fences(raw)
        narratives = json.loads(cleaned)
    except Exception as exc:
        print(f"Warning: Gemini API call failed ({exc}). Using mock fallback data.")
        # Fallback if API fails (429 quota, etc.) so the demo doesn't break
        narratives = []
        for row in sorted_rows:
            wid = row["worker_id"]
            if row["status"] == "RED":
                notes = f"Low active ratio ({round(row['active_ratio']*100)}%) with few bursts limits overall efficiency."
            elif row["status"] == "AMBER":
                notes = f"Moderate performance, consistent bursts but could improve active time."
            else:
                notes = f"Excellent metrics with {row['motion_bursts']} motion bursts and steady activity."
            
            narratives.append({
                "worker_id": wid,
                "score": round(row["efficiency_score"], 2),
                "rank": row["rank"],
                "status": row["status"],
                "narrative": notes
            })

    # Merge narratives into our rows (keyed by worker_id)
    narrative_map = {item["worker_id"]: item.get("narrative", "") for item in narratives}

    result: list[dict] = []
    for row in sorted_rows:
        wid = row["worker_id"]
        result.append(
            {
                "worker_id":           wid,
                "division":            row.get("division", "Unknown"),
                "shift":               row.get("shift", "Unknown"),
                "score":               round(row["efficiency_score"], 2),
                "rank":                row["rank"],
                "status":              row["status"],
                "active_ratio":        round(row["active_ratio"], 4),
                "motion_bursts":       row["motion_bursts"],
                "mean_acc_mag":        round(row["mean_acc_mag"], 4),
                "mean_gyro_mag":       round(row["mean_gyro_mag"], 4),
                "duration_s":          round(row["duration_s"], 2),
                "avg_burst_duration_s": round(row["avg_burst_duration_s"], 4),
                "narrative":           narrative_map.get(wid, ""),
            }
        )

    # Save report payload
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "report_payload.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    return result
