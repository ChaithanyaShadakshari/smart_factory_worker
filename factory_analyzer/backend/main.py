"""
main.py – FastAPI application entrypoint.
"""
from pathlib import Path
from dotenv import load_dotenv
import os
import shutil
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")
from typing import List
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import (
    get_connection,
    init_db,
    insert_metrics,
    insert_session,
    insert_worker_session,
    upsert_worker,
)
from imu_parser import load_device_map, parse_imu_file
from agent import run_agent
from excel_writer import generate_excel_report


BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Factory Efficiency Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    init_db()


# Mount static files under /static
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html not found")
    return FileResponse(index_path)


@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    device_map: UploadFile = File(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    session_id = uuid4().hex
    session_dir = OUTPUT_DIR / "uploads" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save device_map if present
    device_map_dict = {}
    if device_map and device_map.filename and getattr(device_map, "file", None):
        if not device_map.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="device_map must be a CSV file.")
        out_csv = session_dir / "device_map.csv"
        with out_csv.open("wb") as fh:
            shutil.copyfileobj(device_map.file, fh)
        try:
            device_map_dict = load_device_map(out_csv)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse device_map: {exc}")

    # Process all IMU TXT files
    workers_parsed = 0
    all_metrics = []

    conn = get_connection()
    try:
        for file in files:
            if not file.filename or not file.filename.endswith(".txt"):
                continue

            out_path = session_dir / file.filename
            with out_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Parse
            met = parse_imu_file(out_path, device_map_dict)
            all_metrics.append(met)
            workers_parsed += 1

            # Save to DB
            upsert_worker(conn, met["worker_id"], met["division"], met["shift"])

            now_str = datetime.now(timezone.utc).isoformat()
            ws_id = insert_worker_session(
                conn,
                session_id,
                met["worker_id"],
                str(out_path),
                met["duration_s"],
                met["sample_count"],
                now_str,
            )

            insert_metrics(
                conn,
                ws_id,
                met["mean_acc_mag"],
                met["mean_gyro_mag"],
                met["active_ratio"],
                met["active_duration_s"],
                met["idle_duration_s"],
                met["motion_bursts"],
                met["avg_burst_duration_s"],
                met["efficiency_score"],
            )

        insert_session(
            conn,
            session_id,
            datetime.now(timezone.utc).isoformat(),
            len(files),
            workers_parsed,
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")
    finally:
        conn.close()

    all_metrics.sort(key=lambda m: m["efficiency_score"], reverse=True)
    return {
        "session_id": session_id,
        "workers_parsed": workers_parsed,
        "preview": all_metrics[:3],
    }


class AnalyzeRequest(BaseModel):
    session_id: str


@app.post("/analyze")
def analyze_session(req: AnalyzeRequest):
    try:
        results = run_agent(req.session_id)
        return {"workers": results}
    except ValueError as ve:
        raise HTTPException(status_code=500, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


class ReportRequest(BaseModel):
    session_id: str


@app.post("/generate-report")
def generate_report(req: ReportRequest):
    # The agent expects output/report_payload.json to be there with the raw data.
    # Alternatively, we could re-run DB + merge json, but since the frontend flow
    # is `/analyze` immediately followed by `/generate-report`, we can just read the payload.
    report_json = OUTPUT_DIR / "report_payload.json"
    if not report_json.exists():
        raise HTTPException(
            status_code=400, detail="Analysis report payload not found. Run /analyze first."
        )

    import json
    try:
        with report_json.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read report payload: {exc}")

    try:
        excel_path = generate_excel_report(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {exc}")

    if not excel_path.exists():
        raise HTTPException(status_code=500, detail="Excel file was not created.")

    return FileResponse(
        path=excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scorecard.xlsx"},
    )


@app.get("/sessions")
def get_sessions():
    conn = get_connection()
    try:
        from database import get_all_sessions
        rows = get_all_sessions(conn)
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}
