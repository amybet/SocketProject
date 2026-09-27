# Helpers shared by the manager and peers

import csv
import ipaddress
import json
import math
from pathlib import Path
import re
import socket
import time
import uuid

MAX_MESSAGE = 60000  
TIMEOUT = 2.0
ATTEMPTS = 3
FIELDS = [
    "event_id", "state", "year", "month_name", "event_type", "cz_type",
    "cz_name", "injuries_direct", "injuries_indirect", "deaths_direct",
    "deaths_indirect", "damage_property", "damage_crops", "tor_f_scale",
]


def port_range(group):
    # assignment's two formulas simplify to 1000 + 500 * group
    if type(group) is not int or group < 1:
        raise ValueError("Group number must be a positive integer.")
    first = 1000 + 500 * group
    if first + 499 > 65535:
        raise ValueError("This group's range would exceed IPv4's port limit.")
    return first, first + 499


def load_group():
    settings = Path(__file__).with_name("settings.json")
    group = json.loads(settings.read_text(encoding="utf-8"))["group_number"]
    if group is None:
        raise ValueError("First run: python configure.py YOUR_GROUP_NUMBER")
    port_range(group)
    return group


def check_port(port, group):
    first, last = port_range(group)
    if type(port) is not int or not first <= port <= last:
        raise ValueError(f"Use port in group's range {first}-{last}.")


def check_name(name):
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z]{1,15}", name) is None:
        raise ValueError("Peer names must contain 1-15 English letters.")


def check_ip(ip):
    ipaddress.IPv4Address(ip)
    if ip == "0.0.0.0":
        raise ValueError("Register your reachable IPv4 address, not 0.0.0.0.")


def request(command, **fields):
    # Retries reuse this ID so a request can be recognized as a duplicate.
    return {"cmd": command, "request_id": uuid.uuid4().hex, **fields}


def trace(who, action, detail):
    print(f"[{time.strftime('%H:%M:%S')}] {who} {action}: {detail}", flush=True)


def send(sock, message, address, who):
    data = json.dumps(message, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_MESSAGE:
        raise ValueError("Message is too large for one UDP datagram.")
    sock.sendto(data, address)
    extra = ""
    if "record" in message:
        extra = f" event={message['record']['event_id']} target={message['target']}"
    if "status" in message:
        extra += f" {message['status']} {message.get('reason', '')}"
    trace(who, "TX", f"{message['cmd']} -> {address[0]}:{address[1]}"
          f" req={message['request_id'][:8]}{extra}")


def receive(sock, who):
    data, address = sock.recvfrom(MAX_MESSAGE + 1)
    if len(data) > MAX_MESSAGE:
        raise ValueError("Oversized message.")
    message = json.loads(data.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("A message must be a JSON object.")
    for key in ("cmd", "request_id"):
        if not isinstance(message.get(key), str) or not message[key]:
            raise ValueError(f"Missing or invalid {key}.")
    trace(who, "RX", f"{message['cmd']} <- {address[0]}:{address[1]}"
          f" req={message['request_id'][:8]}")
    return message, address


def prime_above(number):
    # try integers until we find the first prime strictly above number
    candidate = max(2, number + 1)
    while any(candidate % d == 0 for d in range(2, math.isqrt(candidate) + 1)):
        candidate += 1
    return candidate


def read_records(path, year):
    #Read csv, keep strings except event_id and year
    records = []
    event_ids = set()
    with open(path, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        headers = [h.strip().lower().replace(" ", "_") for h in reader.fieldnames or []]
        if headers != FIELDS:
            raise ValueError("Expected the course CSV's 14 fields in the specified order.")
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Wrong field count on CSV line {line}.")
            record = dict(zip(FIELDS, row.values()))
            record["event_id"] = int(record["event_id"])
            record["year"] = int(record["year"])
            if record["event_id"] < 0 or record["year"] != year:
                raise ValueError(f"Invalid event ID or wrong year on CSV line {line}.")
            if record["event_id"] in event_ids:
                raise ValueError(f"Duplicate event ID on CSV line {line}.")
            event_ids.add(record["event_id"])
            records.append(record)
    return records
