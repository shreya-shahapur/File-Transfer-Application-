import socket
import hashlib
import os
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
import time

SERVER_IP = "127.0.0.1"
PORT = 5002
CHUNK_SIZE = 2048

PROGRESS_DIR = "server_progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)


def progress_path(filename):
    return os.path.join(PROGRESS_DIR, filename + ".progress.json")

def load_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            raw = json.load(f)
        return {int(k): bytes.fromhex(v) for k, v in raw.items()}
    return {}

def save_chunk_to_disk(filename, seq, chunk):
    path = progress_path(filename)
    raw = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            raw = json.load(f)
    raw[str(seq)] = chunk.hex()
    with open(path, "w") as f:
        json.dump(raw, f)

def clear_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        os.remove(path)


class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP File Transfer — Server")
        self.root.geometry("780x600")
        self.root.configure(bg="#F5F6FA")
        self.root.resizable(False, False)

        self.server_thread = None
        self.running = False
        self.server_socket = None

        self.files_data = {}
        self.transfer_finished = {}

        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#1A1D2E", height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="UDP FILE TRANSFER", font=("Courier New", 13, "bold"),
                 fg="#FFFFFF", bg="#1A1D2E").place(x=24, rely=0.5, anchor="w")
        tk.Label(header, text="SERVER", font=("Courier New", 13, "bold"),
                 fg="#4ECDC4", bg="#1A1D2E").place(x=200, rely=0.5, anchor="w")

        self.status_dot = tk.Label(header, text="●", font=("Courier New", 14),
                                   fg="#E74C3C", bg="#1A1D2E")
        self.status_dot.place(relx=0.9, rely=0.5, anchor="center")
        self.status_label = tk.Label(header, text="OFFLINE", font=("Courier New", 9),
                                     fg="#888", bg="#1A1D2E")
        self.status_label.place(relx=0.95, rely=0.5, anchor="center")

        ctrl = tk.Frame(self.root, bg="#ECEEF5", pady=10)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text=f"  Listening on  {SERVER_IP}:{PORT}",
                 font=("Courier New", 10), fg="#555", bg="#ECEEF5").pack(side="left", padx=12)

        self.start_btn = tk.Button(ctrl, text="▶  START SERVER", font=("Courier New", 10, "bold"),
                                   bg="#2ECC71", fg="white", relief="flat",
                                   padx=14, pady=6, cursor="hand2",
                                   command=self.start_server)
        self.start_btn.pack(side="right", padx=10)

        self.stop_btn = tk.Button(ctrl, text="■  STOP", font=("Courier New", 10, "bold"),
                                  bg="#E74C3C", fg="white", relief="flat",
                                  padx=14, pady=6, cursor="hand2",
                                  command=self.stop_server, state="disabled")
        self.stop_btn.pack(side="right", padx=4)

        mid = tk.Frame(self.root, bg="#F5F6FA")
        mid.pack(fill="x", padx=20, pady=(14, 0))

        tk.Label(mid, text="FILES RECEIVED", font=("Courier New", 9, "bold"),
                 fg="#999", bg="#F5F6FA").pack(anchor="w")

        self.file_frame = tk.Frame(mid, bg="#F5F6FA")
        self.file_frame.pack(fill="x", pady=(6, 0))

        self.file_widgets = {}

        log_frame = tk.Frame(self.root, bg="#F5F6FA")
        log_frame.pack(fill="both", expand=True, padx=20, pady=14)

        tk.Label(log_frame, text="EVENT LOG", font=("Courier New", 9, "bold"),
                 fg="#999", bg="#F5F6FA").pack(anchor="w")

        self.log = scrolledtext.ScrolledText(
            log_frame, font=("Courier New", 9), bg="#1A1D2E", fg="#C8D0E0",
            relief="flat", bd=0, wrap="word", height=14,
            insertbackground="white"
        )
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self.log.configure(state="disabled")

        self.log.tag_config("info",    foreground="#C8D0E0")
        self.log.tag_config("success", foreground="#2ECC71")
        self.log.tag_config("warn",    foreground="#F39C12")
        self.log.tag_config("error",   foreground="#E74C3C")
        self.log.tag_config("chunk",   foreground="#4ECDC4")

    def log_msg(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}]  {msg}\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_status(self, online: bool):
        if online:
            self.status_dot.config(fg="#2ECC71")
            self.status_label.config(fg="#2ECC71", text="ONLINE ")
        else:
            self.status_dot.config(fg="#E74C3C")
            self.status_label.config(fg="#888", text="OFFLINE")

    def add_file_widget(self, filename):
        if filename in self.file_widgets:
            return
        row = tk.Frame(self.file_frame, bg="#ECEEF5", pady=6, padx=10)
        row.pack(fill="x", pady=3)

        tk.Label(row, text=filename, font=("Courier New", 10, "bold"),
                 fg="#1A1D2E", bg="#ECEEF5", width=20, anchor="w").pack(side="left")

        pvar = tk.DoubleVar(value=0)
        bar = ttk.Progressbar(row, variable=pvar, maximum=100, length=300, mode="determinate")
        bar.pack(side="left", padx=12)

        slbl = tk.Label(row, text="Receiving…", font=("Courier New", 9),
                        fg="#888", bg="#ECEEF5", width=18, anchor="w")
        slbl.pack(side="left")

        self.file_widgets[filename] = (row, pvar, slbl)

    def update_file_progress(self, filename, pct, status_text, color="#888"):
        if filename not in self.file_widgets:
            self.root.after(0, lambda: self.add_file_widget(filename))
            return
        _, pvar, slbl = self.file_widgets[filename]
        pvar.set(pct)
        slbl.config(text=status_text, fg=color)

    def start_server(self):
        self.running = True
        self.files_data = {}
        self.transfer_finished = {}
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.set_status(True)
        self.log_msg("Server started — waiting for connections…", "success")
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.set_status(False)
        self.log_msg("Server stopped.", "warn")

    def _run_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.bind((SERVER_IP, PORT))
            self.server_socket.settimeout(1.0)
        except Exception as e:
            self.root.after(0, lambda: self.log_msg(f"Cannot bind: {e}", "error"))
            self.root.after(0, self.stop_server)
            return

        while self.running:
            try:
                data, addr = self.server_socket.recvfrom(CHUNK_SIZE + 256)
            except socket.timeout:
                continue
            except Exception:
                break

            if data.startswith(b"RESUME|"):
                filename = data.decode().split("|")[1]
                self.root.after(0, lambda f=filename: self.log_msg(f"Resume request: {f}", "info"))
                self.root.after(0, lambda f=filename: self.add_file_widget(f))

                saved = load_progress(filename)
                if saved:
                    self.files_data[filename] = saved
                    last_seq = max(saved.keys()) + 1
                    self.root.after(0, lambda f=filename, n=len(saved):
                        self.log_msg(f"Loaded {n} chunks from disk for {f} — resuming", "warn"))
                    self.root.after(0, lambda f=filename, n=len(saved):
                        self.update_file_progress(f, 0, f"Resumed ({n} cached)", "#F39C12"))
                else:
                    self.files_data[filename] = {}
                    last_seq = 0

                self.server_socket.sendto(str(last_seq).encode(), addr)
                continue

            if data.startswith(b"END|"):
                filename = data.decode().split("|")[1]
                self.root.after(0, lambda f=filename: self.log_msg(f"END signal for {f}", "warn"))

                if filename in self.files_data:
                    with open("received_" + filename, "wb") as file:
                        for i in sorted(self.files_data[filename].keys()):
                            file.write(self.files_data[filename][i])
                    self.root.after(0, lambda f=filename: self.log_msg(f"File written: received_{f}", "success"))
                    total = len(self.files_data[filename])
                    self.root.after(0, lambda f=filename, t=total:
                        self.update_file_progress(f, 100, f"✓ {t} chunks", "#2ECC71"))

                self.transfer_finished[filename] = True
                continue

            if data.startswith(b"HASH|"):
                parts = data.decode().split("|")
                filename, client_hash = parts[1], parts[2]

                if self.transfer_finished.get(filename, False):
                    with open("received_" + filename, "rb") as f:
                        server_hash = hashlib.md5(f.read()).hexdigest()

                    if client_hash == server_hash:
                        clear_progress(filename)
                        self.root.after(0, lambda f=filename:
                            self.log_msg(f"✓ Hash verified — progress cleared for {f}", "success"))
                        self.root.after(0, lambda f=filename:
                            self.update_file_progress(f, 100, "✓ Verified", "#2ECC71"))
                    else:
                        self.root.after(0, lambda f=filename:
                            self.log_msg(f"✗ Hash MISMATCH for {f}", "error"))
                        self.root.after(0, lambda f=filename:
                            self.update_file_progress(f, 100, "✗ Corrupted", "#E74C3C"))
                continue

            try:
                filename_b, seq_b, chunk = data.split(b"|", 2)
                filename = filename_b.decode()
                seq = int(seq_b)

                if filename not in self.files_data:
                    self.files_data[filename] = {}
                    self.root.after(0, lambda f=filename: self.add_file_widget(f))

                if seq not in self.files_data[filename]:
                    self.files_data[filename][seq] = chunk
                    save_chunk_to_disk(filename, seq, chunk)

                self.server_socket.sendto(str(seq).encode(), addr)

                received = len(self.files_data[filename])
                self.root.after(0, lambda f=filename, s=seq, r=received:
                    self.log_msg(f"Chunk {s} of {f}  ({r} total so far)", "chunk"))

            except Exception as e:
                self.root.after(0, lambda err=e: self.log_msg(f"Packet error: {err}", "error"))


if __name__ == "__main__":
    root = tk.Tk()
    app = ServerGUI(root)
    root.mainloop()
