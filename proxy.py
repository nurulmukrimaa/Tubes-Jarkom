"""
proxy.py — Proxy Server (Forward + Cache)
Tugas Besar Jaringan Komputer — Fakultas Informatika, Universitas Telkom

Listening  → port 8080
Forward ke → webserver port 8000

Cara pakai:
  1. Jalankan webserver.py dulu
  2. Jalankan proxy.py
  3. Jalankan client.py
"""

import socket
import threading
import os
import datetime

# ─────────────────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────────────────
PROXY_HOST  = "0.0.0.0"
PROXY_PORT  = 8080
SERVER_HOST = "127.0.0.1"   # ← ganti IP laptop webserver jika beda perangkat
SERVER_PORT = 8000
BUFFER_SIZE = 4096
TIMEOUT     = 5              # detik tunggu response dari webserver

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Lock untuk cegah race condition saat baca/tulis cache bersamaan
cache_lock = threading.Lock()

# ─────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag:<8}] {msg}")

# ─────────────────────────────────────────────────────────
# HELPER: nama file cache dari URL path
# Contoh: /css/style.css → cache/css_style.css.cache
# ─────────────────────────────────────────────────────────
def cache_filename(path):
    safe = path.strip("/").replace("/", "_") or "root_index.html"
    return os.path.join(CACHE_DIR, safe + ".cache")

# ─────────────────────────────────────────────────────────
# HELPER: parse URL path dari raw HTTP request bytes
# ─────────────────────────────────────────────────────────
def parse_path(raw_bytes):
    try:
        first_line = raw_bytes.decode(errors="replace").split("\r\n")[0]
        parts = first_line.split()
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return "/"

# ─────────────────────────────────────────────────────────
# HELPER: buat error response sederhana
# (502/504 — proxy tidak bisa relay file status dari server
#  karena server mungkin tidak bisa dihubungi)
# ─────────────────────────────────────────────────────────
def make_error_response(code, reason, description):
    body = (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
        f'<title>{code} {reason}</title>'
        f'<style>body{{font-family:sans-serif;text-align:center;'
        f'background:linear-gradient(135deg,#667eea,#764ba2);'
        f'color:white;min-height:100vh;display:flex;'
        f'justify-content:center;align-items:center;}}'
        f'.box{{background:rgba(255,255,255,0.15);padding:60px 40px;'
        f'border-radius:20px;backdrop-filter:blur(12px);}}'
        f'h1{{font-size:80px;margin:0;}}a{{color:white;}}</style>'
        f'</head><body><div class="box">'
        f'<h1>{code}</h1><h2>{reason}</h2>'
        f'<p>{description}</p>'
        f'<p><a href="/">← Kembali ke Home</a></p>'
        f'</div></body></html>'
    ).encode()
    header = (
        f"HTTP/1.1 {code} {reason}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode()
    return header + body

# ─────────────────────────────────────────────────────────
# HANDLE SATU CLIENT
# ─────────────────────────────────────────────────────────
def handle_client(conn, addr):
    t_start = datetime.datetime.now()

    try:
        # ── Terima request dari client ──────────────────────
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
        if path == "/" or path == "":
            path = "/index.html"

        cache_file = cache_filename(path)

        # ── CEK CACHE ───────────────────────────────────────
        cached_response = None
        with cache_lock:
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    cached_response = f.read()

        if cached_response is not None:
            # CACHE HIT
            conn.sendall(cached_response)
            elapsed = (datetime.datetime.now() - t_start).total_seconds() * 1000
            log("HIT", f"{addr[0]} | {path} | {elapsed:.1f} ms (dari cache)")
            conn.close()
            return

        # ── CACHE MISS: forward ke webserver ────────────────
        log("MISS", f"{addr[0]} | {path} | forward ke server...")

        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.settimeout(TIMEOUT)
            srv.connect((SERVER_HOST, SERVER_PORT))
            srv.sendall(raw_request)

            # Terima seluruh response dari webserver
            response = b""
            while True:
                chunk = srv.recv(BUFFER_SIZE)
                if not chunk:
                    break
                response += chunk
            srv.close()

        except socket.timeout:
            elapsed = (datetime.datetime.now() - t_start).total_seconds() * 1000
            log("504", f"{addr[0]} | {path} | webserver timeout ({elapsed:.0f}ms)")
            conn.sendall(make_error_response(
                504, "Gateway Timeout",
                "Web server tidak merespons dalam batas waktu yang ditentukan."
            ))
            conn.close()
            return

        except ConnectionRefusedError:
            elapsed = (datetime.datetime.now() - t_start).total_seconds() * 1000
            log("504", f"{addr[0]} | {path} | webserver refused ({elapsed:.0f}ms)")
            conn.sendall(make_error_response(
                504, "Gateway Timeout",
                "Tidak dapat terhubung ke web server. Pastikan webserver.py berjalan."
            ))
            conn.close()
            return

        except Exception as e:
            log("502", f"{addr[0]} | {path} | error: {e}")
            conn.sendall(make_error_response(
                502, "Bad Gateway",
                f"Terjadi kesalahan saat menghubungi web server: {e}"
            ))
            conn.close()
            return

        # Validasi: response tidak boleh kosong
        if not response:
            log("502", f"{addr[0]} | {path} | response kosong dari server")
            conn.sendall(make_error_response(
                502, "Bad Gateway",
                "Web server mengirim response kosong."
            ))
            conn.close()
            return

        # ── Simpan ke cache HANYA jika response 200 OK ──────
        first_line = response.split(b"\r\n")[0].decode(errors="replace")
        if "200" in first_line:
            with cache_lock:
                with open(cache_file, "wb") as f:
                    f.write(response)

        # Kirim response ke client
        conn.sendall(response)
        elapsed = (datetime.datetime.now() - t_start).total_seconds() * 1000
        log("MISS", f"{addr[0]} | {path} | {first_line} | {elapsed:.1f} ms → cache saved")

    except socket.timeout:
        log("TIMEOUT", f"{addr[0]} | timeout saat terima request dari client")
    except BrokenPipeError:
        log("BROKEN", f"{addr[0]} | koneksi terputus")
    except Exception as e:
        log("ERR", f"{addr[0]} | {e}")
    finally:
        try:
            conn.close()
        except:
            pass

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy.bind((PROXY_HOST, PROXY_PORT))
    proxy.listen(20)

    print("=" * 60)
    print("  PROXY.PY — Forward + Cache")
    print(f"  Listening → 0.0.0.0:{PROXY_PORT}")
    print(f"  Forward   → {SERVER_HOST}:{SERVER_PORT}")
    print(f"  Cache dir → {CACHE_DIR}")
    print("=" * 60)
    print()
    print("  Urutan start yang benar:")
    print("    1. python webserver.py")
    print("    2. python proxy.py        ← (ini)")
    print("    3. python client.py")
    print()

    while True:
        try:
            conn, addr = proxy.accept()
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            )
            t.start()
            log("CONN", f"Client {addr[0]}:{addr[1]} terhubung | thread aktif: {threading.active_count()-1}")
        except Exception as e:
            log("ERR", f"Accept error: {e}")