#!/usr/bin/env python3
"""Run the EOP-0001 form staging preview on loopback only."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO


class StagingRequestHandler(SimpleHTTPRequestHandler):
    """Read-only static handler with defensive response headers."""

    server_version = "EOP0001Staging/0.1"

    def end_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'none'; form-action 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; object-src 'none'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self) -> None:
        self.send_error(405, "Staging server is read-only")

    def do_PUT(self) -> None:
        self.send_error(405, "Staging server is read-only")

    def do_PATCH(self) -> None:
        self.send_error(405, "Staging server is read-only")

    def do_DELETE(self) -> None:
        self.send_error(405, "Staging server is read-only")

    def copyfile(
        self,
        source: BinaryIO,
        outputfile: BinaryIO,
    ) -> None:
        super().copyfile(source, outputfile)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.host != "127.0.0.1":
        print("Refusing to bind Stage 4I staging to a non-loopback host.")
        return 2
    if not 1024 <= args.port <= 65535:
        print("Port must be between 1024 and 65535.")
        return 2

    repo_root = Path.cwd().resolve()
    directory = repo_root / "sandbox/eop_0001_form_staging"
    if not directory.is_dir():
        print(f"Staging directory not found: {directory}")
        return 2

    handler = partial(
        StagingRequestHandler,
        directory=str(directory),
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"Stage 4I local preview: http://{args.host}:{args.port}/index.html"
    )
    print("No network submission or server-side storage is enabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStage 4I preview stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
