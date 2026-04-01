"""
TREND RADAR — Server Locale
============================
Avvia con: python server.py
Poi apri il browser su: http://localhost:8000

Serve la dashboard HTML e i risultati JSON dell'ultima scansione.
"""

import http.server
import socketserver
import json
import os
import glob
from datetime import datetime

PORT = 8000


class TrendRadarHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):

        # ── /api/results → ritorna l'ultimo JSON di scansione ──────
        if self.path == "/api/results":
            self.serve_latest_results()

        # ── /api/keywords → ritorna le keyword salvate ─────────────
        elif self.path == "/api/keywords":
            self.serve_keywords()

        # ── tutto il resto → file statici (HTML, CSS, JS) ──────────
        else:
            super().do_GET()

    def serve_latest_results(self):
        """Trova e serve il file JSON più recente."""
        json_files = glob.glob("radar_results_*.json")

        if not json_files:
            # Nessuna scansione ancora — ritorna stato vuoto
            self.send_json({
                "status": "empty",
                "message": "Nessuna scansione ancora. Esegui: python trend_radar.py",
                "scan_date": None,
                "keywords_used": [],
                "signals": []
            })
            return

        # Prende il file più recente per nome (formato YYYYMMDD_HHMM)
        latest = sorted(json_files)[-1]

        try:
            with open(latest, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["status"] = "ok"
            data["source_file"] = latest
            self.send_json(data)
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)})

    def serve_keywords(self):
        """Serve le keyword salvate."""
        if os.path.exists("keywords.txt"):
            with open("keywords.txt", "r", encoding="utf-8") as f:
                keywords = [l.strip() for l in f if l.strip()]
        else:
            keywords = []
        self.send_json({"keywords": keywords})

    def send_json(self, data: dict):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Stampa solo le richieste API, non i file statici
        if "/api/" in args[0]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"{timestamp} │ {args[0]}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 50)
    print("  TREND RADAR — Server Locale")
    print("=" * 50)
    print(f"  Apri il browser su: http://localhost:{PORT}")
    print(f"  Cartella: {os.getcwd()}")
    print("  Premi Ctrl+C per fermare")
    print("=" * 50)

    with socketserver.TCPServer(("", PORT), TrendRadarHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer fermato.")
