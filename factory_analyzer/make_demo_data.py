"""
make_demo_data.py - Generate mock IMU txt files and a device_map.csv
"""
import json
import math
import random
from pathlib import Path

# Worker Config:
#   W001, W002 -> GREEN (score > 75)
#   W003-W007 -> AMBER (score 60-75)
#   W008-W010 -> RED (score < 60)

WORKERS = {
    "W001": {"division": "AssemblyA", "shift": "Morning", "profile": "GREEN"},
    "W002": {"division": "AssemblyA", "shift": "Morning", "profile": "GREEN"},
    "W003": {"division": "AssemblyB", "shift": "Morning", "profile": "AMBER"},
    "W004": {"division": "AssemblyB", "shift": "Morning", "profile": "AMBER"},
    "W005": {"division": "AssemblyB", "shift": "Evening", "profile": "AMBER"},
    "W006": {"division": "AssemblyC", "shift": "Evening", "profile": "AMBER"},
    "W007": {"division": "AssemblyC", "shift": "Evening", "profile": "AMBER"},
    "W008": {"division": "QualityCheck", "shift": "Morning", "profile": "RED"},
    "W009": {"division": "QualityCheck", "shift": "Evening", "profile": "RED"},
    "W010": {"division": "Packaging", "shift": "Morning", "profile": "RED"},
}

NUM_LINES = 500
BASE_INTERVAL_US = 30_000

# Base gravity
GRAVITY = 9.81


def generate_worker_file(out_dir: Path, worker_id: str, info: dict):
    profile = info["profile"]

    # Profile heuristics
    if profile == "GREEN":
        active_prob = 0.85
        burst_freq = 0.05  # high freq of new bursts
        gyro_peak = 2.0
        acc_spike = 6.0
    elif profile == "AMBER":
        active_prob = 0.55
        burst_freq = 0.03
        gyro_peak = 1.0
        acc_spike = 4.0
    else:  # RED
        active_prob = 0.25
        burst_freq = 0.01
        gyro_peak = 0.5
        acc_spike = 2.0

    filename = out_dir / f"{worker_id}-0001.txt"
    t_us = 0
    in_burst = False
    burst_time_left = 0

    with filename.open("w", encoding="utf-8") as fh:
        for _ in range(NUM_LINES):
            t_us += int(random.gauss(BASE_INTERVAL_US, 1000))

            # State machine for activity
            if in_burst:
                burst_time_left -= 1
                if burst_time_left <= 0:
                    in_burst = False
            else:
                # chance to start a burst
                if random.random() < burst_freq:
                    # we want active_prob total activity, rough heuristic
                    in_burst = True
                    burst_length = random.randint(10, 50)
                    burst_time_left = burst_length
                
                # Baseline override if profile demands high baseline
                if random.random() < active_prob * 0.1:
                    in_burst = True
                    burst_time_left = random.randint(5, 10)

            # Generate reading
            if in_burst:
                ax = random.uniform(-acc_spike, acc_spike)
                ay = random.uniform(-acc_spike, acc_spike)
                az = GRAVITY + random.uniform(-acc_spike, acc_spike)
                
                gx = random.uniform(-gyro_peak, gyro_peak)
                gy = random.uniform(-gyro_peak, gyro_peak)
                gz = random.uniform(-gyro_peak, gyro_peak)
            else:
                # idle / tiny movement
                ax = random.uniform(-0.5, 0.5)
                ay = random.uniform(-0.5, 0.5)
                az = GRAVITY + random.uniform(-0.5, 0.5)
                
                gx = random.uniform(-0.1, 0.1)
                gy = random.uniform(-0.1, 0.1)
                gz = random.uniform(-0.1, 0.1)

            entry = {
                "t_us": t_us,
                "acc": [round(ax, 3), round(ay, 3), round(az, 3)],
                "gyro": [round(gx, 3), round(gy, 3), round(gz, 3)]
            }
            fh.write(json.dumps(entry) + "\n")


def make_demo_data():
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Make .txt files
    for wid, info in WORKERS.items():
        generate_worker_file(data_dir, wid, info)

    # Make device_map.csv
    csv_path = data_dir / "device_map.csv"
    with csv_path.open("w", encoding="utf-8") as fh:
        fh.write("device_id,worker_id,division,shift\n")
        for wid, info in WORKERS.items():
            fh.write(f"{wid},{wid},{info['division']},{info['shift']}\n")

    print(f"Generated {len(WORKERS)} files and device_map.csv in {data_dir.resolve()}")


if __name__ == "__main__":
    make_demo_data()
