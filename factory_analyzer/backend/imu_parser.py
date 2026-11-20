"""
imu_parser.py – Parse IMU .txt files and compute efficiency metrics.
"""
import json
import math
from pathlib import Path


# ── Constants ──────────────────────────────────────────────────────────────────
ACC_THRESHOLD  = 9.5    # m/s²
GYRO_THRESHOLD = 0.3    # rad/s
MERGE_GAP_US   = 1_000_000   # 1 second in microseconds
MIN_BURST_US   = 500_000     # 0.5 seconds in microseconds


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def parse_imu_file(
    file_path: str | Path,
    device_map: dict[str, dict] | None = None,
) -> dict:
    """
    Parse one IMU .txt file and return a metrics dict.

    Parameters
    ----------
    file_path  : path to the .txt file
    device_map : optional mapping of device_id -> {worker_id, division, shift}
    """
    file_path = Path(file_path)
    stem = file_path.stem  # e.g. "W042-0001"
    device_id = stem.split("-")[0]  # e.g. "W042"

    # Resolve worker metadata from device_map or fall back to device_id
    if device_map and device_id in device_map:
        meta = device_map[device_id]
        worker_id = meta.get("worker_id", device_id)
        division  = meta.get("division", "Unknown")
        shift     = meta.get("shift", "Unknown")
    else:
        worker_id = device_id
        division  = "Unknown"
        shift     = "Unknown"

    # ── Parse lines ──────────────────────────────────────────────────────────
    samples: list[dict] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                t_us = int(obj["t_us"])
                ax, ay, az = map(float, obj["acc"])
                gx, gy, gz = map(float, obj["gyro"])
                acc_mag  = math.sqrt(ax**2 + ay**2 + az**2)
                gyro_mag = math.sqrt(gx**2 + gy**2 + gz**2)
                active   = acc_mag > ACC_THRESHOLD or gyro_mag > GYRO_THRESHOLD
                samples.append(
                    {
                        "t_us": t_us,
                        "acc_mag": acc_mag,
                        "gyro_mag": gyro_mag,
                        "active": active,
                    }
                )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                # Skip malformed lines silently
                continue

    if not samples:
        return _empty_result(worker_id, division, shift)

    # Sort by timestamp (defensive)
    samples.sort(key=lambda s: s["t_us"])

    total_duration_us = samples[-1]["t_us"] - samples[0]["t_us"]
    total_duration_s  = total_duration_us / 1_000_000 if total_duration_us > 0 else 1e-6
    sample_count      = len(samples)

    mean_acc_mag  = sum(s["acc_mag"]  for s in samples) / sample_count
    mean_gyro_mag = sum(s["gyro_mag"] for s in samples) / sample_count

    # ── Build activity intervals ──────────────────────────────────────────────
    # Each interval: [start_us, end_us]
    raw_intervals: list[list[int]] = []
    in_burst = False
    burst_start = 0

    for i, s in enumerate(samples):
        if s["active"]:
            if not in_burst:
                in_burst = True
                burst_start = s["t_us"]
            # Extend the burst end to current timestamp
            burst_end = s["t_us"]
        else:
            if in_burst:
                raw_intervals.append([burst_start, burst_end])
                in_burst = False

    # Close a trailing burst
    if in_burst:
        raw_intervals.append([burst_start, samples[-1]["t_us"]])

    # ── Merge gaps < 1 second ─────────────────────────────────────────────────
    merged: list[list[int]] = []
    for iv in raw_intervals:
        if merged and iv[0] - merged[-1][1] < MERGE_GAP_US:
            merged[-1][1] = max(merged[-1][1], iv[1])
        else:
            merged.append([iv[0], iv[1]])

    # ── Discard bursts < 0.5 seconds ─────────────────────────────────────────
    valid_bursts = [iv for iv in merged if iv[1] - iv[0] >= MIN_BURST_US]

    # ── Compute metrics ───────────────────────────────────────────────────────
    active_duration_us = sum(iv[1] - iv[0] for iv in valid_bursts)
    active_duration_s  = active_duration_us / 1_000_000
    idle_duration_s    = total_duration_s - active_duration_s
    active_ratio       = active_duration_s / total_duration_s
    motion_bursts      = len(valid_bursts)
    avg_burst_duration_s = active_duration_s / max(1, motion_bursts)

    bursts_per_minute  = (motion_bursts / total_duration_s) * 60 if total_duration_s > 0 else 0

    efficiency_score = _clamp(
        0.50 * (active_ratio * 100)
        + 0.25 * min(100.0, (bursts_per_minute / 4.0) * 100)
        + 0.25 * min(100.0, (mean_gyro_mag / 1.0) * 100),
        0.0,
        100.0,
    )

    return {
        "worker_id":           worker_id,
        "division":            division,
        "shift":               shift,
        "file_path":           str(file_path),
        "duration_s":          total_duration_s,
        "sample_count":        sample_count,
        "mean_acc_mag":        mean_acc_mag,
        "mean_gyro_mag":       mean_gyro_mag,
        "active_ratio":        active_ratio,
        "active_duration_s":   active_duration_s,
        "idle_duration_s":     idle_duration_s,
        "motion_bursts":       motion_bursts,
        "avg_burst_duration_s": avg_burst_duration_s,
        "efficiency_score":    efficiency_score,
    }


def _empty_result(worker_id: str, division: str, shift: str) -> dict:
    return {
        "worker_id":           worker_id,
        "division":            division,
        "shift":               shift,
        "file_path":           "",
        "duration_s":          0.0,
        "sample_count":        0,
        "mean_acc_mag":        0.0,
        "mean_gyro_mag":       0.0,
        "active_ratio":        0.0,
        "active_duration_s":   0.0,
        "idle_duration_s":     0.0,
        "motion_bursts":       0,
        "avg_burst_duration_s": 0.0,
        "efficiency_score":    0.0,
    }


def load_device_map(csv_path: str | Path) -> dict[str, dict]:
    """
    Load device_map.csv → {device_id: {worker_id, division, shift}}.
    Header: device_id,worker_id,division,shift
    """
    import csv

    device_map: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            device_map[row["device_id"].strip()] = {
                "worker_id": row["worker_id"].strip(),
                "division":  row["division"].strip(),
                "shift":     row["shift"].strip(),
            }
    return device_map
