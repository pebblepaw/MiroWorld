from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class OasisRequestHandler(BaseHTTPRequestHandler):
    server_version = "OASISSidecar/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health"}:
            self._write_json(
                200,
                {
                    "status": "ok",
                    "service": "oasis-sidecar",
                    "path": self.path,
                },
            )
            return

        self._write_json(404, {"detail": "Not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Keep container logs quiet unless the caller explicitly redirects stdout/stderr.
        return

    def _write_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OASIS sidecar health server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8001, help="TCP port to bind.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), OasisRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
