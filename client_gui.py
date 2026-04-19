import socket
import hashlib
import sys
import os
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk, filedialog
import time

SERVER_IP = "127.0.0.1"
PORT = 5002
CHUNK_SIZE = 1024
TIMEOUT = 1
WINDOW_SIZE = 4

PROGRESS_DIR = "client_progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)


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


class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP File Transfer — Client")
        self.root.geometry("780x640")
        self.root.configure(bg="#F5F6FA")
        self.root.resizable(False, False)

        self.files_to_send = []
        self.sending = False

        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#1A1D2E", height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="UDP FILE TRANSFER", font=("Courier New", 13, "bold"),
                 fg="#FFFFFF", bg="#1A1D2E").place(x=24, rely=0.5, anchor="w")
        tk.Label(header, text="CLIENT", font=("Courier New", 13, "bold"),
                 fg="#F39C12", bg="#1A1D2E").place(x=200, rely=0.5, anchor="w")

        tk.Label(header, text=f"→  {SERVER_IP}:{PORT}", font=("Courier New", 10),
                 fg="#888", bg="#1A1D2E").place(relx=0.65, rely=0.5, anchor="w")

        sel = tk.Frame(self.root, bg="#ECEEF5", pady=12)
        sel.pack(fill="x")

        tk.Label(sel, text="  FILES TO SEND", font=("Courier New", 9, "bold"),
                 fg="#999", bg="#ECEEF5").pack(anchor="w", padx=12)

        list_row = tk.Frame(sel, bg="#ECEEF5")
        list_row.pack(fill="x", padx=12, pady=(6, 0))

        self.file_listbox = tk.Listbox(
            list_row, font=("Courier New", 10), bg="#1A1D2E", fg="#C8D0E0",
            selectbackground="#4ECDC4", selectforeground="#1A1D2E",
            relief="flat", bd=0, height=4, activestyle="none"
        )
        self.file_listbox.pack(side="left", fill="x", expand=True)

        btn_col = tk.Frame(list_row, bg="#ECEEF5")
        btn_col.pack(side="left", padx=(8, 0))

        tk.Button(btn_col, text="+ Add Files", font=("Courier New", 9, "bold"),
                  bg="#3498DB", fg="white", relief="flat", padx=10, pady=5,
                  cursor="hand2", command=self.add_files).pack(fill="x", pady=2)

        tk.Button(btn_col, text="✕ Remove", font=("Courier New", 9, "bold"),
                  bg="#95A5A6", fg="white", relief="flat", padx=10, pady=5,
                  cursor="hand2", command=self.remove_file).pack(fill="x", pady=2)

        tk.Button(btn_col, text="⌫ Clear All", font=("Courier New", 9, "bold"),
                  bg="#95A5A6", fg="white", relief="flat", padx=10, pady=5,
                  cursor="hand2", command=self.clear_files).pack(fill="x", pady=2)

        ctrl = tk.Frame(self.root, bg="#F5F6FA", pady=10)
        ctrl.pack(fill="x", padx=20)

        self.send_btn = tk.Button(ctrl, text="▶  SEND FILES", font=("Courier New", 11, "bold"),
                                  bg="#F39C12", fg="white", relief="flat",
                                  padx=18, pady=8, cursor="hand2",
                                  command=self.start_transfer)
        self.send_btn.pack(side="left")

        self.cancel_btn = tk.Button(ctrl, text="■  CANCEL", font=("Courier New", 11, "bold"),
                                    bg="#E74C3C", fg="white", relief="flat",
                                    padx=18, pady=8, cursor="hand2",
                                    command=self.cancel_transfer, state="disabled")
        self.cancel_btn.pack(side="left", padx=10)

        prog_frame = tk.Frame(self.root, bg="#F5F6FA")
        prog_frame.pack(fill="x", padx=20, pady=(10, 0))

        tk.Label(prog_frame, text="TRANSFER PROGRESS", font=("Courier New", 9, "bold"),
                 fg="#999", bg="#F5F6FA").pack(anchor="w")

        self.prog_area = tk.Frame(prog_frame, bg="#F5F6FA")
        self.prog_area.pack(fill="x", pady=(6, 0))

        self.progress_widgets = {}

        log_frame = tk.Frame(self.root, bg="#F5F6FA")
        log_frame.pack(fill="both", expand=True, padx=20, pady=12)

        tk.Label(log_frame, text="EVENT LOG", font=("Courier New", 9, "bold"),
                 fg="#999", bg="#F5F6FA").pack(anchor="w")

        self.log = scrolledtext.ScrolledText(
            log_frame, font=("Courier New", 9), bg="#1A1D2E", fg="#C8D0E0",
            relief="flat", bd=0, wrap="word", height=12,
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
        self.log.configure(state="normal")
        self.log.insert("end", f"{msg}\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Select files to send")
        for p in paths:
            if p not in self.files_to_send:
                self.files_to_send.append(p)
                self.file_listbox.insert("end", os.path.basename(p))

    def remove_file(self):
        sel = self.file_listbox.curselection()
        if sel:
            idx = sel[0]
            self.file_listbox.delete(idx)
            self.files_to_send.pop(idx)

    def clear_files(self):
        self.file_listbox.delete(0, "end")
        self.files_to_send.clear()

    def _add_progress_row(self, filename):
        if filename in self.progress_widgets:
            return
        row = tk.Frame(self.prog_area, bg="#ECEEF5", pady=6, padx=10)
        row.pack(fill="x", pady=3)

        tk.Label(row, text=filename, font=("Courier New", 10, "bold"),
                 fg="#1A1D2E", bg="#ECEEF5", width=20, anchor="w").pack(side="left")

        pvar = tk.DoubleVar(value=0)
        bar = ttk.Progressbar(row, variable=pvar, maximum=100, length=300, mode="determinate")
        bar.pack(side="left", padx=12)

        slbl = tk.Label(row, text="Queued", font=("Courier New", 9),
                        fg="#888", bg="#ECEEF5", width=18, anchor="w")
        slbl.pack(side="left")

        self.progress_widgets[filename] = (pvar, slbl)

    def update_progress(self, filename, pct, text, color="#888"):
        if filename not in self.progress_widgets:
            return
        pvar, slbl = self.progress_widgets[filename]
        pvar.set(pct)
        slbl.config(text=text, fg=color)

    def start_transfer(self):
        if not self.files_to_send:
            self.log_msg("No files selected.", "warn")
            return
        if self.sending:
            return

        self.sending = True
        self.send_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")

        for w in self.prog_area.winfo_children():
            w.destroy()
        self.progress_widgets.clear()

        for fp in self.files_to_send:
            fn = os.path.basename(fp)
            self._add_progress_row(fn)

            saved = load_client_progress(fn)
            if saved:
                self.root.after(0, lambda f=fn, n=len(saved):
                    self.log_msg(f"💾 Found saved progress for {f}: {n} chunks already ACKed", "warn"))

        t = threading.Thread(target=self._send_all, daemon=True)
        t.start()

    def cancel_transfer(self):
        self.sending = False
        self.send_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.root.after(0, lambda: self.log_msg("Transfer cancelled — progress saved to disk.", "warn"))

    def _send_all(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(TIMEOUT)

        for filepath in list(self.files_to_send):
            if not self.sending:
                break
            filename = os.path.basename(filepath)
            self.root.after(0, lambda f=filename: self.log_msg(f"📁 Sending file: {f}", "info"))
            self.root.after(0, lambda f=filename: self.update_progress(f, 0, "Connecting…", "#F39C12"))

            try:
                self.root.after(0, lambda: self.log_msg("📤 Sending RESUME request...", "info"))
                client.sendto(f"RESUME|{filename}".encode(), (SERVER_IP, PORT))
                resp, _ = client.recvfrom(1024)
                start_seq = int(resp.decode())
                self.root.after(0, lambda s=start_seq:
                    self.log_msg(f"⬅ Server says start from seq {s}", "info"))
            except socket.timeout:
                start_seq = 0
                self.root.after(0, lambda:
                    self.log_msg("⚠ No response from server, starting from 0", "warn"))

            packets = []
            try:
                with open(filepath, "rb") as f:
                    seq = 0
                    while True:
                        data = f.read(CHUNK_SIZE)
                        if not data:
                            break
                        packet = f"{filename}|{seq}".encode() + b"|" + data
                        packets.append(packet)
                        seq += 1
            except FileNotFoundError:
                self.root.after(0, lambda fp=filepath:
                    self.log_msg(f"⚠ File not found: {fp}", "error"))
                continue

            total = len(packets)
            self.root.after(0, lambda t=total:
                self.log_msg(f"📁 Total chunks prepared: {t}", "info"))

            acked = load_client_progress(filename)
            base = start_seq
            while base in acked:
                base += 1
            next_seq = base

            if acked:
                pct = (base / total) * 100
                self.root.after(0, lambda f=filename, p=pct, b=base, t=total:
                    self.update_progress(f, p, f"Resumed {b}/{t}", "#F39C12"))

            while base < total and self.sending:
                while next_seq < base + WINDOW_SIZE and next_seq < total:
                    if next_seq not in acked:
                        client.sendto(packets[next_seq], (SERVER_IP, PORT))
                        self.root.after(0, lambda s=next_seq:
                            self.log_msg(f"📤 Sending chunk {s}", "chunk"))
                    next_seq += 1

                try:
                    ack, _ = client.recvfrom(1024)
                    ack_seq = int(ack.decode())
                    acked.add(ack_seq)
                    save_client_progress(filename, acked)

                    while base in acked:
                        base += 1

                    pct = (base / total) * 100
                    bar_len = 20
                    filled = int(bar_len * base // total)
                    bar = "█" * filled + "-" * (bar_len - filled)
                    self.root.after(0, lambda s=ack_seq, b=bar, p=pct:
                        self.log_msg(f"✅ ACK received for {s}", "success"))
                    self.root.after(0, lambda bb=bar, pp=pct:
                        self.log_msg(f"📊 Progress: |{bb}| {pp:.2f}%", "info"))

                    self.root.after(0, lambda f=filename, p=pct, b=base, t=total:
                        self.update_progress(f, p, f"{b}/{t} chunks", "#F39C12"))

                except socket.timeout:
                    self.root.after(0, lambda:
                        self.log_msg("⏰ Timeout! Resending unACKed packets...", "warn"))
                    for i in range(base, next_seq):
                        if i not in acked:
                            client.sendto(packets[i], (SERVER_IP, PORT))
                            self.root.after(0, lambda s=i:
                                self.log_msg(f"🔁 Resending chunk {s}", "warn"))

            if not self.sending:
                self.root.after(0, lambda f=filename:
                    self.log_msg(f"⚠ Paused — progress saved for {f}", "warn"))
                break

            client.sendto(f"END|{filename}".encode(), (SERVER_IP, PORT))
            self.root.after(0, lambda: self.log_msg("🏁 END signal sent", "info"))

            with open(filepath, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            client.sendto(f"HASH|{filename}|{file_hash}".encode(), (SERVER_IP, PORT))
            self.root.after(0, lambda: self.log_msg("🔐 Hash sent", "success"))

            clear_client_progress(filename)
            self.root.after(0, lambda f=filename:
                self.update_progress(f, 100, "✓ Complete", "#2ECC71"))

        client.close()
        self.sending = False
        self.root.after(0, lambda: self.send_btn.config(state="normal"))
        self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))
        self.root.after(0, lambda: self.log_msg("🎉 File transfer completed successfully!", "success"))


if __name__ == "__main__":
    root = tk.Tk()
    app = ClientGUI(root)
    root.mainloop()
