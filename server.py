import socket
import hashlib
import os
import json

SERVER_IP = "127.0.0.1"
PORT = 5002
CHUNK_SIZE = 2048

PROGRESS_DIR = "server_progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((SERVER_IP, PORT))

print("🚀 Server is listening...")

files_data = {}
transfer_finished = {}


def progress_path(filename):
    return os.path.join(PROGRESS_DIR, filename + ".progress.json")


def load_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            raw = json.load(f)
        return {int(k): bytes.fromhex(v) for k, v in raw.items()}
    return {}


def save_chunk(filename, seq, chunk):
    path = progress_path(filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            raw = json.load(f)
    else:
        raw = {}
    raw[str(seq)] = chunk.hex()
    with open(path, "w") as f:
        json.dump(raw, f)


def clear_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        os.remove(path)


while True:
    data, addr = server.recvfrom(CHUNK_SIZE)

    print(f"\n📥 Received: {data[:50]}...")

    if data.startswith(b"RESUME|"):
        filename = data.decode().split("|")[1]
        print(f"📩 Resume request for {filename}")

        saved = load_progress(filename)
        if saved:
            files_data[filename] = saved
            last_seq = max(saved.keys()) + 1
            print(f"💾 Loaded {len(saved)} chunks from disk for {filename}")
        else:
            files_data[filename] = {}
            last_seq = 0

        print(f"➡ Sending start sequence: {last_seq}")
        server.sendto(str(last_seq).encode(), addr)
        continue

    if data.startswith(b"END|"):
        filename = data.decode().split("|")[1]
        print(f"🏁 END signal received for {filename}")

        if filename in files_data:
            with open("received_" + filename, "wb") as file:
                for i in sorted(files_data[filename].keys()):
                    file.write(files_data[filename][i])
            print(f"📁 File '{filename}' written successfully")

        transfer_finished[filename] = True
        continue

    if data.startswith(b"HASH|"):
        parts = data.decode().split("|")
        filename = parts[1]
        client_hash = parts[2]

        print(f"🔐 Hash received for {filename}")

        if transfer_finished.get(filename, False):
            with open("received_" + filename, "rb") as f:
                server_hash = hashlib.md5(f.read()).hexdigest()

            print(f"Client Hash : {client_hash}")
            print(f"Server Hash : {server_hash}")

            if client_hash == server_hash:
                print(f"✅ File '{filename}' integrity verified")
                clear_progress(filename)
            else:
                print(f"❌ File '{filename}' corrupted")
        else:
            print("⚠ File not yet finalized before hash check")

        continue

    try:
        filename_b, seq_b, chunk = data.split(b"|", 2)
        filename = filename_b.decode()
        seq = int(seq_b)

        print(f"📦 Chunk {seq} of {filename}, size = {len(chunk)} bytes")

        if filename not in files_data:
            files_data[filename] = {}

        if seq not in files_data[filename]:
            files_data[filename][seq] = chunk
            save_chunk(filename, seq, chunk)

        server.sendto(str(seq).encode(), addr)
        print(f"✅ ACK sent for seq {seq}")

    except Exception as e:
        print("⚠ Error processing packet:", e)
