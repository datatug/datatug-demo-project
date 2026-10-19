#!/usr/bin/env python3
"""Serve an already built DataTug app on loopback with SPA route fallback."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("browser_dir", type=Path, help="DataTug dist/apps/datatug-app/browser")
    parser.add_argument("--port", type=int, default=4200)
    args = parser.parse_args()
    root = args.browser_dir.resolve()
    if not (root / "index.html").is_file():
        parser.error(f"no built DataTug index.html in {root}")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    class SPA(SimpleHTTPRequestHandler):
        def __init__(self, *handler_args: object, **handler_kwargs: object) -> None:
            super().__init__(*handler_args, directory=str(root), **handler_kwargs)

        def _route(self) -> bool:
            requested = unquote(urlsplit(self.path).path)
            target = (root / requested.lstrip("/")).resolve()
            if not target.is_relative_to(root):
                self.send_error(403)
                return False
            if not target.is_file() and not PurePosixPath(requested).suffix:
                self.path = "/index.html"
            return True

        def do_GET(self) -> None:
            if self._route():
                super().do_GET()

        def do_HEAD(self) -> None:
            if self._route():
                super().do_HEAD()

        def log_message(self, _format: str, *_args: object) -> None:
            # Query strings can contain investigation identifiers or owner tokens.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), SPA)
    print(f"Serving built DataTug at http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
