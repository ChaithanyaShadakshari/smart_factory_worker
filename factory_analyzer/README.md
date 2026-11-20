# Factory Efficiency Analyzer

This project is a PoC for analyzing worker efficiency based on IMU sensor data. 
It uses **FastAPI** on the backend, **SQLite** for storing parsed session data, and the **Gemini 2.0 Flash** API via the `google-generativeai` SDK to generate qualitative efficiency narratives. The final results are exported to a styled Excel scorecard using `openpyxl`.

## Architecture Diagram

```ascii
  .txt files (IMU) → FastAPI → imu_parser → SQLite
                                     ↓
                           agent.py (Gemini API)
                                     ↓
                         excel_writer → scorecard.xlsx
```

## Setup and Run

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Generate demo data:**
   ```bash
   # From the project root:
   python make_demo_data.py
   ```
   This creates a `data/` folder containing 10 simulated `.txt` IMU files and a `device_map.csv`.

3. **Set API key:**
   - **Windows:**
     ```cmd
     set GEMINI_API_KEY=your_key_here
     ```
   - **Linux/Mac/PowerShell:**
     ```bash
     $env:GEMINI_API_KEY="your_key_here"  # PowerShell
     # or
     export GEMINI_API_KEY=your_key_here  # Bash/Zsh
     ```

4. **Start server:**
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

5. **Open browser:**
   Navigate to [http://localhost:8000](http://localhost:8000)

6. **Usage:**
   - Drag and drop the generated `.txt` files from the `data/` folder.
   - Upload the optional `device_map.csv`.
   - Click "Analyze & Generate Report".
   - Download the generated `.xlsx` Excel Report.

## Note
This PoC demonstrates the full data pipeline and AI agent layer.
The computer-use layer — where an agent opens and formats Excel natively on Windows — is the next phase planned for the live ideathon demo.
