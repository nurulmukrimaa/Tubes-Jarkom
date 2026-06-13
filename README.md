# Tugas Besar Jaringan Komputer

## Kelompok 5

Anggota:

1. Nurul Mukrima Amir
2. Nafthali Fathania Raissa Putri Yulianto
3. Hilwa Aulia Naajaha

---

## Deskripsi

Project ini merupakan implementasi arsitektur Client – Proxy – Server menggunakan Socket Programming Python.

Sistem terdiri dari:

- Web Server (TCP)
- Proxy Server dengan Cache
- Client HTTP
- UDP Echo Server
- Pengukuran QoS (RTT, Packet Loss, Throughput, dan Jitter)

Selain itu, tersedia website sederhana yang berisi materi mengenai:

- OSI Model
- TCP/IP Model
- Quality of Service (QoS)
- Socket Programming

---

## Struktur Folder

```text
Tubes-Jarkom
│
├── assets
├── cache
├── css
├── status
│
├── client.py
├── proxy.py
├── webserver.py
│
├── index.html
├── osi.html
├── tcpip.html
├── qos.html
├── implementation.html
│
└── README.md
```

---

## Cara Menjalankan

### Jalankan Web Server

```bash
python webserver.py
```

### Jalankan Proxy Server

```bash
python proxy.py
```

### Jalankan Client

Mode HTTP:

```bash
python client.py --mode tcp
```

Mode QoS:

```bash
python client.py --mode udp
```

---

## Fitur

- HTTP Server menggunakan TCP Socket
- UDP Echo Server
- Proxy Forwarding
- Cache HIT dan MISS
- Multi-threading
- Pengukuran QoS
- Custom Error Page (404, 500, 502, 504)

---

## Teknologi

- Python 3
- Socket Programming
- HTML
- CSS
- JavaScript

---

Tugas Besar Jaringan Komputer  
Fakultas Informatika - Universitas Telkom
