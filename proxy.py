"""
proxy.py — Proxy Server (Forwarding + Caching)
Tugas Besar Jaringan Komputer
Fakultas Informatika - Universitas Telkom

Jalankan: python proxy.py
Listening  -> port 8080
Forward ke -> webserver port 8000
"""

import socket
import threading
import os
import datetime

# ── Konfigurasi ──────────────────────────────────────────────────────────────
PROXY_HOST   = "0.0.0.0"
PROXY_PORT   = 8080
SERVER_HOST  = "127.0.0.1"   # ← ganti IP webserver kalau beda laptop
SERVER_PORT  = 8000
BUFFER_SIZE  = 4096
TIMEOUT      = 5              # detik tunggu webserver
CACHE_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

# ── Buat folder cache ─────────────────────────────────────────────────────────
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Lock untuk cache (hindari race condition) ─────────────────────────────────
cache_lock = threading.Lock()

# ── Logging ───────────────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}")

# ── Nama file cache dari URL path ─────────────────────────────────────────────
def cache_filename(path):
    safe = path.strip("/").replace("/", "_") or "root"
    return os.path.join(CACHE_DIR, safe + ".cache")

# ── Error responses ───────────────────────────────────────────────────────────
def response_502():
    body = b"<h1>502 Bad Gateway</h1><p>Server mengembalikan respons tidak valid.</p>"
    return (
        b"HTTP/1.1 502 Bad Gateway\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n\r\n" + body
    )

def response_504():
    body = b"<h1>504 Gateway Timeout</h1><p>Web server tidak merespons.</p>"
    return (
        b"HTTP/1.1 504 Gateway Timeout\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n\r\n" + body
    )

# ── Parse path dari raw HTTP request ─────────────────────────────────────────
def parse_path(raw_bytes):
    try:
        first_line = raw_bytes.decode(errors="replace").split("\r\n")[0]
        parts = first_line.split()
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return "/"

# ── Handle satu client ────────────────────────────────────────────────────────
def handle_client(conn, addr):
    t_start = datetime.datetime.now()
    try:
        # Terima request dari client
        raw_request = b""
        conn.settimeout(TIMEOUT)
        while b"\r\n\r\n" not in raw_request:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw_request += chunk

        if not raw_request:
            conn.close()
            return

        path = parse_path(raw_request)
        if path == "/":
            path = "/index.html"

        cache_file = cache_filename(path)
        cache_hit  = False

        # ── Cek cache ──────────────────────────────────────────────────────────
        with cache_lock:
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    cached_response = f.read()
                cache_hit = True

        if cache_hit:
            conn.sendall(cached_response)
            elapsed = (datetime.datetime.now() - t_start).total_seconds() * 1000
            log("CACHE-HIT", f"{addr[0]} | {path} | {elapsed:.1f}ms")
            conn.close()
            return

        # ── Cache MISS: forward ke web server ─────────────────────────────────
        try:
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv_sock.settimeout(TIMEOUT)
            srv_sock.connect((SERVER_HOST, SERVER_PORT))
            srv_sock.sendall(raw_request)

            # Terima seluruh response
            response = b""
            while True:
                chunk = srv_sock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                response += chunk
            srv_sock.close()

        except socket.timeout:
            log("TIMEOUT", f"{addr[0]} | {path} | webserver tidak merespons")
            conn.sendall(response_504())
            conn.close()
            return
        except ConnectionRefusedError:
            log("REFUSED", f"{addr[0]} | {path} | webserver tidak bisa dikoneksi")
            conn.sendall(response_504())
            conn.close()
            return
        except Exception as e:
            log("ERROR", f"{addr[0]} | {path} | {e}")
            conn.sendall(response_502())
            conn.close()
            return

        # Validasi response dari server
        if not response:
            conn.sendall(response_502())
            conn.close()
            return

        # Simpan ke cache
        with cache_lock:
            with open(cache_file, "wb") as f:
                f.write(response)

        conn.sendall(response)
        elapsed = (datetime.datetime.now() - t_start).total_seconds() * 1000
        log("CACHE-MISS", f"{addr[0]} | {path} | {elapsed:.1f}ms → disimpan ke cache")

    except Exception as e:
        log("ERR", f"{addr[0]} | Exception: {e}")
    finally:
        try:
            conn.close()
        except:
            pass

# ── Main proxy loop ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy.bind((PROXY_HOST, PROXY_PORT))
    proxy.listen(20)

    print("=" * 55)
    print("  PROXY.PY — Forward + Cache")
    print(f"  Listening → 0.0.0.0:{PROXY_PORT}")
    print(f"  Forward   → {SERVER_HOST}:{SERVER_PORT}")
    print(f"  Cache dir → {CACHE_DIR}")
    print("=" * 55)

    while True:
        conn, addr = proxy.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()
        log("CONNECT", f"Client {addr[0]}:{addr[1]} | thread aktif: {threading.active_count()-1}")
