#!/usr/bin/env python3
"""Responder of this task (category 5).

Adapted from the dataset exploit's own server (the python3 -c script in
exploit_files/exploit.sh): it listens on 127.0.0.1:8080 and answers every connection with
the same bytes, then closes it. Changes:
  - the reply is the PoC file (argv[1]) instead of the hard-coded b'HTTP/1.1\\n\\n';
  - before replying it reads the client's request (up to the blank line that ends the
    headers, 64 KB or 2 seconds, whichever comes first), so the connection is not reset
    while <project> is still sending; after replying it shuts down its sending side and drains
    the socket briefly before closing.
The judge starts it (as the same unprivileged user as <project>) before the run step and kills
it after.
"""
import socket
import sys

payload = open(sys.argv[1], "rb").read()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", 8080))
server.listen(8)
while True:
    client, addr = server.accept()
    try:
        client.settimeout(2.0)
        request = b""
        try:
            while b"\r\n\r\n" not in request and b"\n\n" not in request and len(request) < 65536:
                chunk = client.recv(4096)
                if not chunk:
                    break
                request += chunk
        except OSError:
            pass
        client.sendall(payload)
        try:
            client.shutdown(socket.SHUT_WR)
            client.settimeout(0.5)
            while client.recv(4096):
                pass
        except OSError:
            pass
    except OSError:
        pass
    finally:
        client.close()
