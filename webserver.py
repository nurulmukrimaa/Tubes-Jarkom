"""
webserver.py — Web Server (TCP HTTP + UDP Echo)
Tugas Besar Jaringan Komputer — Fakultas Informatika, Universitas Telkom

TCP HTTP  → port 8000
UDP Echo  → port 9000

Struktur folder (semua di direktori yang sama dengan webserver.py):
  index.html, osi.html, tcpip.html, qos.html, implementation.html
  css/style.css
  assets/iflab.png, network.png, osi.png, tcpip.png, tcpip-flow.png, osi.mp4
  status/404.html, 500.html, 502.html, 504.html
"""

import socket
import threading
import os
import datetime

# ─────────────────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────────────────
TCP_HOST    = "0.0.0.0"
TCP_PORT    = 8000
UDP_HOST    = "0.0.0.0"
UDP_PORT    = 9000
BUFFER_SIZE = 4096
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico":  "image/x-icon",
    ".mp4":  "video/mp4",
    ".txt":  "text/plain",
    ".json": "application/json",
}

# ─────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag:<8}] {msg}")

# ─────────────────────────────────────────────────────────
# HELPER: baca file error page custom dari status/
# ─────────────────────────────────────────────────────────
def read_status_page(code):
    """Baca status/xxx.html. Fallback ke teks polos jika tidak ada."""
    path = os.path.join(BASE_DIR, "status", f"{code}.html")
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>{code} Error</h1>".encode()

# ─────────────────────────────────────────────────────────
# HELPER: bangun HTTP response
# ─────────────────────────────────────────────────────────
def build_response(status_code, status_text, content_type, body_bytes):
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return header.encode() + body_bytes

# ─────────────────────────────────────────────────────────
# HANDLE SATU KONEKSI TCP
# ─────────────────────────────────────────────────────────
def handle_tcp_client(conn, addr):
    try:
        # Terima request sampai header selesai
        raw = b""
        conn.settimeout(10)
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw += chunk

        if not raw:
            return

        # ── Parse request line ──────────────────────────────
        first_line = raw.decode(errors="replace").split("\r\n")[0]
        parts = first_line.split()

        if len(parts) < 2:
            conn.sendall(build_response(
                500, "Internal Server Error",
                "text/html; charset=utf-8",
                read_status_page(500)
            ))
            return

        method = parts[0]
        path   = parts[1]

        # Default ke index.html
        if path == "/" or path == "":
            path = "/index.html"

        # ── Keamanan: cegah path traversal ─────────────────
        safe_path = os.path.normpath(path.lstrip("/"))
        if safe_path.startswith(".."):
            conn.sendall(build_response(
                404, "Not Found",
                "text/html; charset=utf-8",
                read_status_page(404)
            ))
            log("TCP", f"{addr[0]} | {method} {path} | 403 Path Traversal Blocked")
            return

        file_path = os.path.join(BASE_DIR, safe_path)

        # ── Tentukan Content-Type ───────────────────────────
        ext          = os.path.splitext(file_path)[1].lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        # ── Serve file ──────────────────────────────────────
        try:
            with open(file_path, "rb") as f:
                body = f.read()
            response = build_response(200, "OK", content_type, body)
            status   = "200 OK"

        except FileNotFoundError:
            body     = read_status_page(404)
            response = build_response(404, "Not Found", "text/html; charset=utf-8", body)
            status   = "404 Not Found"

        except PermissionError:
            body     = read_status_page(500)
            response = build_response(500, "Internal Server Error", "text/html; charset=utf-8", body)
            status   = "500 Permission Denied"

        except Exception as e:
            log("ERR", f"File error: {e}")
            body     = read_status_page(500)
            response = build_response(500, "Internal Server Error", "text/html; charset=utf-8", body)
            status   = "500 Internal Server Error"

        conn.sendall(response)
        log("TCP", f"{addr[0]} | {method} {path} | {status} | {len(body)} bytes")

    except socket.timeout:
        log("TCP", f"{addr[0]} | timeout saat menerima request")
    except BrokenPipeError:
        log("TCP", f"{addr[0]} | koneksi terputus oleh client")
    except Exception as e:
        log("ERR", f"{addr[0]} | exception: {e}")
        try:
            conn.sendall(build_response(
                500, "Internal Server Error",
                "text/html; charset=utf-8",
                read_status_page(500)
            ))
        except:
            pass
    finally:
        try:
            conn.close()
        except:
            pass

# ─────────────────────────────────────────────────────────
# TCP SERVER LOOP
# ─────────────────────────────────────────────────────────
def run_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(20)
    log("TCP", f"HTTP Server siap di port {TCP_PORT}")
    log("TCP", f"Serving files dari: {BASE_DIR}")

    while True:
        try:
            conn, addr = server.accept()
            t = threading.Thread(
                target=handle_tcp_client,
                args=(conn, addr),
                daemon=True
            )
            t.start()
            log("THREAD", f"New thread untuk {addr[0]}:{addr[1]} | aktif: {threading.active_count()-1}")
        except Exception as e:
            log("ERR", f"Accept error: {e}")

# ─────────────────────────────────────────────────────────
# UDP ECHO SERVER LOOP
# ─────────────────────────────────────────────────────────
def run_udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((UDP_HOST, UDP_PORT))
    log("UDP", f"Echo Server siap di port {UDP_PORT}")

    while True:
        try:
            data, addr = server.recvfrom(BUFFER_SIZE)
            server.sendto(data, addr)  # echo identik
            log("UDP", f"Echo → {addr[0]}:{addr[1]} | payload: {data.decode(errors='replace')}")
        except Exception as e:
            log("UDP-ERR", str(e))

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  WEBSERVER.PY — TCP HTTP + UDP Echo")
    print(f"  TCP HTTP  → 0.0.0.0:{TCP_PORT}")
    print(f"  UDP Echo  → 0.0.0.0:{UDP_PORT}")
    print(f"  Root dir  → {BASE_DIR}")
    print("=" * 60)
    print()

    # Cek keberadaan file-file utama
    required = ["index.html", "osi.html", "tcpip.html", "qos.html",
                "implementation.html", "css/style.css",
                "status/404.html", "status/500.html",
                "status/502.html", "status/504.html"]
    missing = [f for f in required if not os.path.exists(os.path.join(BASE_DIR, f))]
    if missing:
        print("[WARN] File berikut tidak ditemukan:")
        for m in missing:
            print(f"       - {m}")
        print()

    # UDP jalan di thread terpisah
    udp_thread = threading.Thread(target=run_udp_server, daemon=True)
    udp_thread.start()

    # TCP di main thread
    run_tcp_server()