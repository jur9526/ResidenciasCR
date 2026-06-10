#!/usr/bin/env python3
"""Dev server with Vercel-style rewrites for local testing."""
import http.server, os
from pathlib import Path

REWRITES = {"/propiedades": "/propiedades.html"}
ROOT = Path(__file__).parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in REWRITES:
            self.path = REWRITES[path]
        super().do_GET()

    def log_message(self, fmt, *args):
        pass  # silenciar logs

if __name__ == "__main__":
    import socketserver
    with socketserver.TCPServer(("", 8080), Handler) as httpd:
        print("Servidor en http://localhost:8080")
        httpd.serve_forever()
