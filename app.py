from __future__ import annotations

import json
import mimetypes
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from fourier_core import run_curve_analysis

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUNS_DIR = STATIC_DIR / "runs"
INDEX_FILE = BASE_DIR / "templates" / "index.html"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def number_value(data: dict, key: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(data.get(key, default))
    except Exception:
        value = float(default)
    return max(float(minimum), min(float(maximum), value))


def integer_value(data: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(data.get(key, default))
    except Exception:
        value = int(default)
    return max(int(minimum), min(int(maximum), value))


def points_to_curve(points: list) -> np.ndarray:
    rows = []
    for item in points:
        if isinstance(item, dict):
            x = item.get("x")
            y = item.get("y")
        else:
            x = item[0]
            y = item[1]
        rows.append([float(x), -float(y)])
    curve = np.asarray(rows, dtype=float)
    if len(curve) < 20:
        raise ValueError("점을 20개 이상 그린 뒤 분석하세요.")
    return curve


def analyze_payload(data: dict) -> dict:
    points = data.get("points", [])
    curve = points_to_curve(points)
    samples = integer_value(data, "samples", 1024, 128, 8192)
    max_order = integer_value(data, "max_order", 80, 1, min(500, samples // 2 - 1))
    perimeter_samples = integer_value(data, "perimeter_samples", 4096, 512, 32768)
    slope_tol = number_value(data, "slope_tol", 0.006, 0.000001, 0.5)
    rmse_tol = number_value(data, "rmse_tol", 0.040, 0.000001, 1.0)
    energy_tol = number_value(data, "energy_tol", 0.985, 0.0, 1.0)
    window = integer_value(data, "window", 3, 1, 20)
    run_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    out_dir = RUNS_DIR / run_id
    summary = run_curve_analysis(
        curve=curve,
        out_dir=out_dir,
        label="drawn curve",
        samples=samples,
        max_order=max_order,
        perimeter_samples=perimeter_samples,
        slope_tol=slope_tol,
        rmse_tol=rmse_tol,
        energy_tol=energy_tol,
        window=window,
    )
    static_base = f"/static/runs/{run_id}"
    return {
        "ok": True,
        "run_id": run_id,
        "summary": summary,
        "images": {
            "curve_reconstruction": f"{static_base}/curve_reconstruction.jpg",
            "error_vs_N": f"{static_base}/error_vs._N.jpg",
        },
        "downloads": {
            "curve_csv": f"{static_base}/drawn_curve_resampled.csv",
            "order_analysis_csv": f"{static_base}/order_analysis.csv",
            "fourier_coefficients_csv": f"{static_base}/fourier_coefficients.csv",
            "summary_json": f"{static_base}/summary.json",
        },
    }


class FourierWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def send_bytes(self, content: bytes, status: int, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload: dict, status: int = 200) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(content, status, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        if path == "/":
            self.send_bytes(INDEX_FILE.read_bytes(), 200, "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            target = (BASE_DIR / path.lstrip("/")).resolve()
            if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
                self.send_bytes(b"Forbidden", 403, "text/plain; charset=utf-8")
                return
            if not target.exists() or not target.is_file():
                self.send_bytes(b"Not found", 404, "text/plain; charset=utf-8")
                return
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_bytes(target.read_bytes(), 200, content_type)
            return
        self.send_bytes(b"Not found", 404, "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/api/analyze":
            self.send_json({"ok": False, "message": "unknown endpoint"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            self.send_json(analyze_payload(data), 200)
        except Exception as exc:
            self.send_json({"ok": False, "message": str(exc)}, 400)


def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    server = ThreadingHTTPServer((host, int(port)), FourierWebHandler)
    url = f"http://{host}:{port}"
    print(f"웹 앱 실행 중: {url}")
    webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    run()
