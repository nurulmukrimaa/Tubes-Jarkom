"""
client.py — HTTP Client (TCP via Proxy) + QoS UDP Pinger
Tugas Besar Jaringan Komputer — Fakultas Informatika, Universitas Telkom

Penggunaan:
  python client.py                            → TCP GET /index.html (default)
  python client.py --mode tcp                 → sama dengan atas
  python client.py --mode tcp --path /osi.html
  python client.py --mode tcp --path /tcpip.html
  python client.py --mode tcp --path /qos.html
  python client.py --mode tcp --path /implementation.html
  python client.py --mode tcp --path /css/style.css
  python client.py --mode udp                 → QoS ping 10 paket
  python client.py --mode udp --count 20      → QoS ping 20 paket

PENTING: Semua request TCP dikirim ke PROXY (port 8080),
         bukan langsung ke webserver. Proxy yg forward ke server.
         UDP dikirim langsung ke webserver port 9000 (QoS test).
"""

import socket
import time
import argparse
import datetime
import statistics

# ─────────────────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────────────────
PROXY_HOST   = "127.0.0.1"   # ← ganti IP laptop proxy jika beda perangkat
PROXY_PORT   = 8080

SERVER_HOST  = "127.0.0.1"   # ← ganti IP laptop webserver jika beda perangkat
UDP_PORT     = 9000

BUFFER_SIZE  = 65535
UDP_TIMEOUT  = 1.0            # detik tunggu echo per paket
UDP_INTERVAL = 0.5            # jeda antar paket (detik)

# ─────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag:<6}] {msg}")

# ─────────────────────────────────────────────────────────
# MODE TCP — HTTP GET via Proxy
# ─────────────────────────────────────────────────────────
def mode_tcp(path="/index.html"):
    print()
    print("=" * 60)
    print(f"  MODE TCP  |  GET {path}")
    print(f"  Via Proxy → {PROXY_HOST}:{PROXY_PORT}")
    print("=" * 60)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((PROXY_HOST, PROXY_PORT))
        log("TCP", f"Terhubung ke proxy {PROXY_HOST}:{PROXY_PORT}")

        # Susun HTTP/1.1 request dengan CRLF
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {PROXY_HOST}:{PROXY_PORT}\r\n"
            f"Connection: close\r\n"
            f"User-Agent: JarkomClient/1.0\r\n"
            f"\r\n"
        )

        t_send = time.time()
        sock.sendall(request.encode())
        log("TCP", f"Request dikirim → GET {path}")

        # Terima seluruh response
        raw = b""
        while True:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                break
            raw += chunk

        elapsed_ms = (time.time() - t_send) * 1000
        sock.close()

        if not raw:
            log("ERR", "Response kosong dari proxy")
            return

        # Pisah header dan body
        if b"\r\n\r\n" in raw:
            header_bytes, body = raw.split(b"\r\n\r\n", 1)
        else:
            header_bytes, body = raw, b""

        header_str  = header_bytes.decode(errors="replace")
        status_line = header_str.split("\r\n")[0]

        print()
        print("─" * 60)
        print(f"  STATUS   : {status_line}")
        print(f"  WAKTU    : {elapsed_ms:.2f} ms")
        print(f"  UKURAN   : {len(body):,} bytes ({len(raw):,} total)")
        print("─" * 60)
        print()
        print("[RESPONSE HEADERS]")
        print(header_str)
        print()
        print("[BODY — 1000 karakter pertama]")
        print()
        print(body[:1000].decode(errors="replace"))

        if len(body) > 1000:
            print(f"\n  ... (+{len(body)-1000} karakter lagi)")

        print()
        print("─" * 60)
        print()

    except ConnectionRefusedError:
        print()
        log("ERR", f"GAGAL: Proxy {PROXY_HOST}:{PROXY_PORT} tidak bisa dikoneksi.")
        log("ERR", "Pastikan proxy.py sudah dijalankan terlebih dahulu.")
    except socket.timeout:
        log("ERR", "TIMEOUT: Proxy tidak merespons dalam 10 detik.")
    except Exception as e:
        log("ERR", f"Exception: {e}")

# ─────────────────────────────────────────────────────────
# MODE UDP — QoS Pinger
# ─────────────────────────────────────────────────────────
def mode_udp(count=10):
    print()
    print("=" * 60)
    print(f"  MODE UDP  |  QoS Pinger")
    print(f"  Target  → {SERVER_HOST}:{UDP_PORT}")
    print(f"  Paket   → {count} paket | timeout: {UDP_TIMEOUT}s | interval: {UDP_INTERVAL}s")
    print("=" * 60)
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)

    rtts         = []
    lost         = 0
    total_bytes  = 0
    t_test_start = time.time()

    for seq in range(1, count + 1):
        send_time = time.time()
        payload   = f"Ping {seq} {send_time:.6f}".encode()

        try:
            sock.sendto(payload, (SERVER_HOST, UDP_PORT))
            t_send = time.time()

            data, server_addr = sock.recvfrom(BUFFER_SIZE)
            t_recv = time.time()

            rtt = (t_recv - t_send) * 1000
            rtts.append(rtt)
            total_bytes += len(data)

            print(f"  [{seq:>3}/{count}] RTT: {rtt:8.3f} ms  | "
                  f"payload: {len(payload)} bytes | echo: OK")

        except socket.timeout:
            lost += 1
            print(f"  [{seq:>3}/{count}] RTT: ---       ms  | "
                  f"Request timed out (>{UDP_TIMEOUT}s)")

        time.sleep(UDP_INTERVAL)

    duration = time.time() - t_test_start
    sock.close()

    # ── Hitung statistik ──────────────────────────────────
    received = count - lost
    loss_pct = (lost / count) * 100

    print()
    print("─" * 60)
    print("  HASIL STATISTIK QoS")
    print("─" * 60)
    print(f"  Paket dikirim      : {count}")
    print(f"  Paket diterima     : {received}")
    print(f"  Paket hilang       : {lost}")
    print(f"  Packet Loss        : {loss_pct:.1f}%")
    print()

    if rtts:
        min_rtt = min(rtts)
        avg_rtt = sum(rtts) / len(rtts)
        max_rtt = max(rtts)

        # Jitter = standar deviasi dari selisih RTT berturut-turut
        if len(rtts) >= 2:
            diffs  = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
            jitter = statistics.stdev(diffs) if len(diffs) > 1 else diffs[0]
        else:
            jitter = 0.0

        # Throughput dalam kbps
        throughput_kbps = (total_bytes * 8) / (duration * 1000) if duration > 0 else 0

        print(f"  RTT Min            : {min_rtt:.3f} ms")
        print(f"  RTT Avg            : {avg_rtt:.3f} ms")
        print(f"  RTT Max            : {max_rtt:.3f} ms")
        print(f"  Jitter             : {jitter:.3f} ms")
        print(f"  Total data rx      : {total_bytes} bytes")
        print(f"  Durasi pengujian   : {duration:.2f} s")
        print(f"  Throughput         : {throughput_kbps:.2f} kbps")
        print()

        # ── Detail RTT per paket (untuk tabel laporan) ─────
        print("  [DETAIL RTT PER PAKET]")
        for i, rtt in enumerate(rtts, 1):
            bar = "█" * int(rtt * 2) if rtt < 30 else "█" * 60 + "..."
            print(f"    Paket {i:>3}: {rtt:7.3f} ms  {bar}")

    else:
        print("  Semua paket hilang — tidak ada data RTT.")
        print("  Pastikan webserver.py berjalan dan UDP port 9000 tidak diblokir firewall.")

    print("─" * 60)
    print()

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Client Tugas Besar Jaringan Komputer",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Contoh penggunaan:\n"
            "  python client.py                          → TCP GET /index.html\n"
            "  python client.py --mode tcp --path /osi.html\n"
            "  python client.py --mode tcp --path /tcpip.html\n"
            "  python client.py --mode tcp --path /qos.html\n"
            "  python client.py --mode tcp --path /implementation.html\n"
            "  python client.py --mode tcp --path /css/style.css\n"
            "  python client.py --mode udp\n"
            "  python client.py --mode udp --count 20\n"
        )
    )
    parser.add_argument(
        "--mode", choices=["tcp", "udp"], default="tcp",
        help="tcp = HTTP GET via proxy | udp = QoS pinger"
    )
    parser.add_argument(
        "--path", default="/index.html",
        help="Path untuk mode TCP (default: /index.html)"
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Jumlah paket UDP (default: 10, minimum tugas: 10)"
    )
    args = parser.parse_args()

    if args.mode == "tcp":
        mode_tcp(path=args.path)
    else:
        mode_udp(count=args.count)