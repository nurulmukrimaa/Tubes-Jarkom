"""
webserver.py — Web Server (TCP HTTP + UDP Echo)
Tugas Besar Jaringan Komputer
Fakultas Informatika - Universitas Telkom

Jalankan: python webserver.py
TCP HTTP  -> port 8000
UDP Echo  -> port 9000
"""

import socket
import threading
import os
import datetime

# ── Konfigurasi ──────────────────────────────────────────────────────────────
TCP_HOST = "0.0.0.0"
TCP_PORT = 8000
UDP_HOST = "0.0.0.0"
UDP_PORT = 9000
BUFFER_SIZE = 4096
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # folder webserver.py

# ── Tipe MIME ─────────────────────────────────────────────────────────────────
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css",
    ".js":   "application/javascript",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".ico":  "image/x-icon",
    ".txt":  "text/plain",
}

# ── Logging ───────────────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}")

# ── HTTP Response Builder ─────────────────────────────────────────────────────
def build_response(status_code, status_text, content_type, body_bytes):
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return header.encode() + body_bytes

def response_404():
    body = b"<h1>404 Not Found</h1><p>File tidak ditemukan di server.</p>"
    return build_response(404, "Not Found", "text/html; charset=utf-8", body)

def response_500():
    body = b"<h1>500 Internal Server Error</h1><p>Terjadi kesalahan pada server.</p>"
    return build_response(500, "Internal Server Error", "text/html; charset=utf-8", body)

# ── Handle satu koneksi TCP ───────────────────────────────────────────────────
def handle_tcp_client(conn, addr):
    try:
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw += chunk

        if not raw:
            return

        # Parse baris pertama: "GET /path HTTP/1.1"
        first_line = raw.decode(errors="replace").split("\r\n")[0]
        parts = first_line.split()
        if len(parts) < 2:
            conn.sendall(response_500())
            return

        method = parts[0]
        path   = parts[1]

        # Default path
        if path == "/":
            path = "/index.html"

        # Keamanan: hindari path traversal
        safe_path = os.path.normpath(path.lstrip("/"))
        file_path = os.path.join(BASE_DIR, safe_path)

        # Tentukan Content-Type
        ext = os.path.splitext(file_path)[1].lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                body = f.read()
            response = build_response(200, "OK", content_type, body)
            status = "200 OK"
        except FileNotFoundError:
            response = response_404()
            status = "404 Not Found"
        except Exception:
            response = response_500()
            status = "500 Internal Server Error"

        conn.sendall(response)
        log("TCP", f"{addr[0]} | {method} {path} | {status}")

    except Exception as e:
        log("TCP-ERR", f"{addr[0]} | Exception: {e}")
        try:
            conn.sendall(response_500())
        except:
            pass
    finally:
        conn.close()

# ── TCP Server Loop ───────────────────────────────────────────────────────────
def run_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(10)
    log("TCP", f"HTTP Server listening on port {TCP_PORT}")

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True)
        t.start()
        log("TCP", f"Thread baru untuk {addr[0]}:{addr[1]} | aktif: {threading.active_count()-1}")

# ── UDP Echo Server Loop ──────────────────────────────────────────────────────
def run_udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((UDP_HOST, UDP_PORT))
    log("UDP", f"Echo Server listening on port {UDP_PORT}")

    while True:
        try:
            data, addr = server.recvfrom(BUFFER_SIZE)
            server.sendto(data, addr)   # echo balik identik
            log("UDP", f"Echo → {addr[0]}:{addr[1]} | payload: {data.decode(errors='replace')}")
        except Exception as e:
            log("UDP-ERR", str(e))

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  WEBSERVER.PY — TCP HTTP + UDP Echo")
    print(f"  TCP  → 0.0.0.0:{TCP_PORT}  (HTTP)")
    print(f"  UDP  → 0.0.0.0:{UDP_PORT}  (QoS Echo)")
    print(f"  Root → {BASE_DIR}")
    print("=" * 55)

    # Jalankan UDP di thread terpisah
    udp_thread = threading.Thread(target=run_udp_server, daemon=True)
    udp_thread.start()

    # TCP jalan di main thread
    run_tcp_server()
