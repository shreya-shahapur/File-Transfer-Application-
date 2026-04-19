# File-Transfer-Application-
A client-server file transfer application by using UDP.

# UDP File Transfer — CN Project

A client-server file transfer application built in Python using UDP sockets. Implements the **Sliding Window Protocol** with support for resume/retransmission and MD5 integrity verification. Includes both a terminal-based version and a Tkinter GUI version.

---

## Features

- UDP-based file transfer using the Sliding Window Protocol (window size = 4)
- Resume support — interrupted transfers pick up from where they left off
- Automatic retransmission on packet timeout
- MD5 hash verification to confirm file integrity after transfer
- Progress tracking saved to disk (JSON) for both client and server
- Tkinter GUI for both client and server with live event logs and progress bars

---

## Project Structure

```
CN PROJECT 2.0/
├── client.py          # Terminal-based client
├── server.py          # Terminal-based server
├── client_gui.py      # GUI client (Tkinter)
├── server_gui.py      # GUI server (Tkinter)
├── client_progress/   # Auto-created: stores client-side resume data
└── server_progress/   # Auto-created: stores server-side received chunks
```

---

## Requirements

- Python 3.x
- Standard library only — no external packages needed (`socket`, `hashlib`, `tkinter`, `threading`, `json`)

---

## How to Run

### Terminal Version

**Start the server first:**
```bash
python server.py
```

**Then run the client:**
```bash
python client.py
```

The client sends `hello.txt` and `file2.txt` by default. Edit the `files_to_send` list in `client.py` to change which files are transferred.

---

### GUI Version

**Start the GUI server:**
```bash
python server_gui.py
```
Click **Start Server** in the window.

**Start the GUI client:**
```bash
python client_gui.py
```
Click **Add Files**, select the files you want to send, then click **Send Files**.

---

## Configuration

These constants can be changed at the top of each file:

| Constant | Default | Description |
|---|---|---|
| `SERVER_IP` | `127.0.0.1` | Server IP address |
| `PORT` | `5002` | UDP port |
| `CHUNK_SIZE` | `1024` (client) | Size of each data chunk in bytes |
| `WINDOW_SIZE` | `4` | Sliding window size |
| `TIMEOUT` | `1` second | Retransmission timeout |

---

## How It Works

1. The client sends a `RESUME` request — the server replies with the last acknowledged sequence number, enabling resume from interruptions.
2. The client splits the file into chunks and sends them using the sliding window protocol.
3. The server sends back an ACK for each chunk received. Unacknowledged chunks are retransmitted after a timeout.
4. Once all chunks are sent, the client sends an `END` signal followed by an MD5 hash of the file.
5. The server verifies the hash against the reassembled file and confirms integrity.
6. Progress is saved to disk on both sides throughout the transfer, so transfers can be safely interrupted and resumed.

---

## Notes

- Run the server before starting the client.
- Both client and server must be on the same network (or the same machine for localhost testing).
- Received files are saved in the server's working directory as `received_<filename>`.
- The `.venv/` folder is not required and should not be uploaded — anyone can recreate it with `python -m venv .venv`.

---

## Author

**shreya-shahapur**  
[GitHub Profile](https://github.com/shreya-shahapur)
