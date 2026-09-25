"""Fast health check endpoint for monitoring Vercel deployment liveness."""

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    """Responds immediately with 200 OK without requiring authentication."""

    def do_GET(self):
        payload = json.dumps({
            "status": "healthy",
            "service": "techyupdates-careers-engine",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)
