# Transfer Guide: Smart Factory Worker

Follow these steps to move this project to another laptop and run it without any manual configuration.

## 1. Prepare the files
Zip the entire `smart_factory_worker` folder. Ensure it includes:
- `run_project.bat`
- `requirements.txt`
- `.env` (contains your Gemini API key)
- `factory_analyzer/`

## 2. On the new laptop
1.  **Install Python**: Download and install the latest Python from [python.org](https://www.python.org/). 
    - *Important*: Make sure to check the box **"Add Python to PATH"** during installation.
2.  **Unzip**: Extract the project folder anywhere.
3.  **Run**: Double-click the `run_project.bat` file.

## 3. What the script does
The `run_project.bat` will automatically:
- Create a virtual environment (`venv`).
- Install all necessary libraries (`fastapi`, `uvicorn`, `google-generativeai`, etc.).
- Start the server on `http://localhost:8000`.

## 4. Accessing the App
Once the script says `Application startup complete`, open your browser and go to:
**http://localhost:8000**

---
**Note on API Key:**
The project is already configured with your API key in the `.env` file. If you want to change it, simply edit the `.env` file with a text editor.
