"""
client.py — HTTP Client (TCP) + QoS UDP Pinger
Tugas Besar Jaringan Komputer
Fakultas Informatika - Universitas Telkom

Penggunaan:
  python client.py --mode tcp              → HTTP GET /index.html
  python client.py --mode tcp --path /page.html
  python client.py --mode udp              → QoS ping 10 paket
  python client.py --mode udp --count 20  → QoS ping 20 paket
"""

import socket
import time
import argparse
import datetime
import statistics

# ── Konfigurasi ──────────────────────────────────────────────────────────────
PROXY_HOST  = "127.0.0.1"   # ← ganti IP proxy kalau beda laptop
PROXY_PORT  = 8080

SERVER_HOST = "127.0.0.1"   # ← ganti IP webserver kalau beda laptop
UDP_PORT    = 9000

BUFFER_SIZE = 65535
UDP_TIMEOUT = 1.0            # detik
UDP_INTERVAL = 0.5           # jeda antar paket (detik)

# ── Logging ───────────────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}")

# ═════════════════════════════════════════════════════════════════════════════
# MODE TCP — HTTP GET via Proxy
# ═════════════════════════════════════════════════════════════════════════════
def mode_tcp(path="/index.html"):
    print("\n" + "=" * 55)
    print(f"  MODE TCP  |  GET {path}")
    print(f"  via Proxy → {PROXY_HOST}:{PROXY_PORT}")
    print("=" * 55)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((PROXY_HOST, PROXY_PORT))

        # Susun HTTP request
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {PROXY_HOST}:{PROXY_PORT}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        sock.sendall(request.encode())
        log("TCP", f"Request dikirim: GET {path}")

        # Terima response
        t_start = time.time()
        raw = b""
        while True:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw += chunk
        elapsed = (time.time() - t_start) * 1000
        sock.close()

        if not raw:
            log("TCP", "Response kosong dari proxy")
            return

        # Pisah header & body
        if b"\r\n\r\n" in raw:
            header_part, body = raw.split(b"\r\n\r\n", 1)
        else:
            header_part, body = raw, b""

        header_str = header_part.decode(errors="replace")
        status_line = header_str.split("\r\n")[0]

        print(f"\n{'─'*55}")
        print(f"  STATUS  : {status_line}")
        print(f"  WAKTU   : {elapsed:.1f} ms")
        print(f"  UKURAN  : {len(body)} bytes")
        print(f"{'─'*55}")
        print("\n[BODY — 500 karakter pertama]\n")
        print(body[:500].decode(errors="replace"))
        print(f"\n{'─'*55}\n")

    except ConnectionRefusedError:
        log("TCP-ERR", f"Proxy {PROXY_HOST}:{PROXY_PORT} tidak bisa dikoneksi. Pastikan proxy.py berjalan.")
    except socket.timeout:
        log("TCP-ERR", "Timeout — proxy tidak merespons.")
    except Exception as e:
        log("TCP-ERR", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# MODE UDP — QoS Pinger
# ═════════════════════════════════════════════════════════════════════════════
def mode_udp(count=10):
    print("\n" + "=" * 55)
    print(f"  MODE UDP  |  QoS Pinger  |  {count} paket")
    print(f"  Target → {SERVER_HOST}:{UDP_PORT}")
    print("=" * 55 + "\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)

    rtts        = []
    lost        = 0
    total_bytes = 0

    for seq in range(1, count + 1):
        timestamp = time.time()
        payload   = f"Ping {seq} {timestamp}".encode()

        try:
            sock.sendto(payload, (SERVER_HOST, UDP_PORT))
            t_send = time.time()

            data, _ = sock.recvfrom(BUFFER_SIZE)
            t_recv  = time.time()

            rtt = (t_recv - t_send) * 1000
            rtts.append(rtt)
            total_bytes += len(data)
            print(f"  Paket {seq:>3} | RTT: {rtt:6.2f} ms | {len(payload)} bytes")

        except socket.timeout:
            lost += 1
            print(f"  Paket {seq:>3} | Request timed out")

        time.sleep(UDP_INTERVAL)

    sock.close()

    # ── Statistik ─────────────────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print("  STATISTIK QoS")
    print(f"{'─'*55}")

    received  = count - lost
    loss_pct  = (lost / count) * 100
    duration  = count * UDP_INTERVAL

    print(f"  Paket dikirim   : {count}")
    print(f"  Paket diterima  : {received}")
    print(f"  Packet Loss     : {loss_pct:.1f}%")

    if rtts:
        min_rtt = min(rtts)
        avg_rtt = sum(rtts) / len(rtts)
        max_rtt = max(rtts)

        # Jitter = standar deviasi selisih RTT berturut-turut
        if len(rtts) >= 2:
            diffs  = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
            jitter = statistics.stdev(diffs) if len(diffs) > 1 else diffs[0]
        else:
            jitter = 0.0

        throughput_kbps = (total_bytes * 8) / (duration * 1000) if duration > 0 else 0

        print(f"  RTT Min         : {min_rtt:.2f} ms")
        print(f"  RTT Avg         : {avg_rtt:.2f} ms")
        print(f"  RTT Max         : {max_rtt:.2f} ms")
        print(f"  Jitter          : {jitter:.2f} ms")
        print(f"  Throughput      : {throughput_kbps:.2f} kbps")
    else:
        print("  Semua paket hilang — tidak ada data RTT.")

    print(f"{'─'*55}\n")

# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client — Tugas Besar Jarkom")
    parser.add_argument("--mode",  choices=["tcp", "udp"], default="tcp",
                        help="tcp = HTTP request, udp = QoS pinger")
    parser.add_argument("--path",  default="/index.html",
                        help="Path HTTP (mode tcp), contoh: /page.html")
    parser.add_argument("--count", type=int, default=10,
                        help="Jumlah paket UDP (mode udp)")
    args = parser.parse_args()

    if args.mode == "tcp":
        mode_tcp(path=args.path)
    else:
        mode_udp(count=args.count)
