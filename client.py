import socket
import hashlib
import sys
import os
import json

SERVER_IP = "127.0.0.1"
PORT = 5002
CHUNK_SIZE = 1024
TIMEOUT = 1
WINDOW_SIZE = 4

PROGRESS_DIR = "client_progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)


def show_progress(base, total):
    percent = (base / total) * 100
    bar_length = 30
    filled = int(bar_length * base // total)
    bar = "█" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\r📊 Progress: |{bar}| {percent:.2f}%")
    sys.stdout.flush()


def progress_path(filename):
    return os.path.join(PROGRESS_DIR, filename + ".client_progress.json")


def save_client_progress(filename, acked_seqs):
    with open(progress_path(filename), "w") as f:
        json.dump({"acked": list(acked_seqs)}, f)


def load_client_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        return set(data.get("acked", []))
    return set()


def clear_client_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        os.remove(path)


client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(TIMEOUT)

files_to_send = ["hello.txt", "file2.txt"]

for filename in files_to_send:

    print(f"\n📁 Sending file: {filename}")

    try:
        print("📤 Sending RESUME request...")
        client.sendto(f"RESUME|{filename}".encode(), (SERVER_IP, PORT))
        start_seq, _ = client.recvfrom(1024)
        start_seq = int(start_seq.decode())
        print(f"⬅ Server says start from seq {start_seq}")
    except socket.timeout:
        print("⚠ No response from server, starting from 0")
        start_seq = 0

    packets = []
    with open(filename, "rb") as file:
        seq = 0
        while True:
            data = file.read(CHUNK_SIZE)
            if not data:
                break
            packet = f"{filename}|{seq}".encode() + b"|" + data
            packets.append(packet)
            seq += 1

    print(f"📁 Total chunks prepared: {len(packets)}")

    base = start_seq
    next_seq = start_seq
    acked = load_client_progress(filename)

    while base in acked:
        base += 1

    while base < len(packets):

        while next_seq < base + WINDOW_SIZE and next_seq < len(packets):
            if next_seq not in acked:
                print(f"📤 Sending chunk {next_seq}")
                client.sendto(packets[next_seq], (SERVER_IP, PORT))
            next_seq += 1

        try:
            ack, _ = client.recvfrom(1024)
            ack_seq = int(ack.decode())

            print(f"✅ ACK received for {ack_seq}")
            acked.add(ack_seq)
            save_client_progress(filename, acked)

            while base in acked:
                base += 1
                show_progress(base, len(packets))

        except socket.timeout:
            print("⏰ Timeout! Resending unACKed packets...")
            for i in range(base, next_seq):
                if i not in acked:
                    print(f"🔁 Resending chunk {i}")
                    client.sendto(packets[i], (SERVER_IP, PORT))

    client.sendto(f"END|{filename}".encode(), (SERVER_IP, PORT))
    print("🏁 END signal sent")

    with open(filename, "rb") as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    client.sendto(f"HASH|{filename}|{file_hash}".encode(), (SERVER_IP, PORT))
    print("🔐 Hash sent")

    clear_client_progress(filename)
    print(f"🧹 Progress cleared for {filename}")

print("🎉 File transfer completed successfully!")
