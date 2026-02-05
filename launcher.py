import subprocess
import sys
import webbrowser
import time
from pathlib import Path

def main():
    # dossier oÃ¹ se trouve app.py
    base_dir = Path(__file__).resolve().parent
    app_path = base_dir / "app.py"

    # Lance Streamlit
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.headless=true"]
    p = subprocess.Popen(cmd)

    # Ouvre le navigateur
    time.sleep(1.5)
    webbrowser.open("http://localhost:8501")

    # Attend que Streamlit se ferme
    p.wait()

if __name__ == "__main__":
    main()

