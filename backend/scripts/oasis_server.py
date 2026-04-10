from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


RUNNER_SCRIPT = Path(__file__).with_name("oasis_reddit_runner.py")


class OasisSidecarServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]):
        super().__init__(server_address, handler_class)
        self.jobs: dict[str, dict[str, object]] = {}
        self.lock = threading.Lock()

    def create_job(self, payload: dict[str, object]) -> dict[str, object]:
        job_id = uuid.uuid4().hex
        work_dir = Path(tempfile.mkdtemp(prefix=f"oasis-sidecar-{job_id}-"))
        input_path = work_dir / "input.json"
        output_path = work_dir / "output.json"
        log_path = work_dir / "run.log"
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        with log_path.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                [sys.executable, str(RUNNER_SCRIPT), str(input_path), str(output_path)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )

        job = {
            "job_id": job_id,
            "status": "running",
            "process": proc,
            "work_dir": str(work_dir),
            "output_path": str(output_path),
            "log_path": str(log_path),
            "result": None,
            "error": None,
        }
        with self.lock:
            self.jobs[job_id] = job
        return self._public_job_payload(job)

    def get_job(self, job_id: str) -> dict[str, object] | None:
        with self.lock:
            job = self.jobs.get(job_id)
        if job is None:
            return None
        self._refresh_job(job)
        return self._public_job_payload(job)

    def cancel_job(self, job_id: str) -> dict[str, object] | None:
        with self.lock:
            job = self.jobs.get(job_id)
        if job is None:
            return None

        proc = job.get("process")
        if isinstance(proc, subprocess.Popen) and proc.poll() is None:
            proc.kill()
        job["status"] = "cancelled"
        job["error"] = str(job.get("error") or "cancelled by caller")
        return self._public_job_payload(job)

    def _refresh_job(self, job: dict[str, object]) -> None:
        status = str(job.get("status") or "")
        if status not in {"running", "queued"}:
            return

        proc = job.get("process")
        if not isinstance(proc, subprocess.Popen):
            job["status"] = "failed"
            job["error"] = "missing process handle"
            return

        rc = proc.poll()
        if rc is None:
            return

        output_path = Path(str(job.get("output_path") or ""))
        log_path = Path(str(job.get("log_path") or ""))
        if rc == 0 and output_path.exists():
            try:
                job["result"] = json.loads(output_path.read_text(encoding="utf-8"))
                job["status"] = "completed"
                return
            except Exception as exc:  # noqa: BLE001
                job["status"] = "failed"
                job["error"] = f"invalid runner output: {exc}"
                return

        tail = ""
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            tail = "\n".join(lines[-40:])
        job["status"] = "failed"
        job["error"] = f"runner exited with code {rc}. {tail}".strip()

    def _public_job_payload(self, job: dict[str, object]) -> dict[str, object]:
        payload = {
            "job_id": str(job.get("job_id") or ""),
            "status": str(job.get("status") or "unknown"),
        }
        if job.get("result") is not None:
            payload["result"] = job["result"]
        if job.get("error") is not None:
            payload["error"] = job["error"]
        return payload


class OasisRequestHandler(BaseHTTPRequestHandler):
    server_version = "OASISSidecar/1.0"

    @property
    def job_server(self) -> OasisSidecarServer:
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health"}:
            with self.job_server.lock:
                statuses = [str(job.get("status") or "unknown") for job in self.job_server.jobs.values()]
            self._write_json(
                200,
                {
                    "status": "ok",
                    "service": "oasis-sidecar",
                    "path": self.path,
                    "jobs": {
                        "running": len([status for status in statuses if status == "running"]),
                        "completed": len([status for status in statuses if status == "completed"]),
                        "failed": len([status for status in statuses if status == "failed"]),
                    },
                },
            )
            return

        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/jobs/", 1)[1].strip("/")
            if not job_id:
                self._write_json(404, {"detail": "Not found"})
                return
            payload = self.job_server.get_job(job_id)
            if payload is None:
                self._write_json(404, {"detail": f"Unknown job: {job_id}"})
                return
            self._write_json(200, payload)
            return

        self._write_json(404, {"detail": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/jobs":
            self._write_json(404, {"detail": "Not found"})
            return

        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._write_json(400, {"detail": str(exc)})
            return

        try:
            job = self.job_server.create_job(payload)
        except Exception as exc:  # noqa: BLE001
            self._write_json(500, {"detail": str(exc)})
            return

        self._write_json(202, job)

    def do_DELETE(self) -> None:  # noqa: N802
        if not self.path.startswith("/jobs/"):
            self._write_json(404, {"detail": "Not found"})
            return

        job_id = self.path.split("/jobs/", 1)[1].strip("/")
        if not job_id:
            self._write_json(404, {"detail": "Not found"})
            return

        payload = self.job_server.cancel_job(job_id)
        if payload is None:
            self._write_json(404, {"detail": f"Unknown job: {job_id}"})
            return
        self._write_json(200, payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("Request body is required.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _write_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OASIS sidecar server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8001, help="TCP port to bind.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = OasisSidecarServer((args.host, args.port), OasisRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
