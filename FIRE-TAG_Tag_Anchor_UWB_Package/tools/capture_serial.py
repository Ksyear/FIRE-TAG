#!/usr/bin/env python3
"""Record the Tag and Anchor 0 serial ports at the same time (macOS / Linux).

Every received line is saved with the host time and the seconds since start,
so the two logs can be lined up. Optionally sends the rescue alert on and off
to Anchor 0 during the capture to test the command path back to the Tag.

  python3 capture_serial.py --tag /dev/cu.usbserial-140 --anchor /dev/cu.usbserial-0001 \
      --seconds 30 --alert-on 10 --alert-off 20 --out ../logs/03_mytest

Writes <out>/tag.log, <out>/anchor0.log and <out>/commands.log. Standard
library only (no pyserial). Close the Arduino serial monitor first.
"""

import argparse
import datetime as dt
import fcntl
import os
import select
import struct
import termios
import time
import tty


def open_port(path):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    tty.setraw(fd)
    attrs = termios.tcgetattr(fd)
    attrs[4] = attrs[5] = termios.B115200
    attrs[2] |= termios.CLOCAL | termios.CREAD
    attrs[2] &= ~getattr(termios, "CRTSCTS", 0)
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    # Keep DTR/RTS low so the ESP32 runs normally; flush bytes received before
    # the speed was set (they decode as garbage otherwise).
    fcntl.ioctl(fd, termios.TIOCMBIC, struct.pack("I", termios.TIOCM_DTR | termios.TIOCM_RTS))
    time.sleep(0.2)
    termios.tcflush(fd, termios.TCIFLUSH)
    return fd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True, help="Tag serial port")
    ap.add_argument("--anchor", required=True, help="Anchor 0 serial port")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--alert-on", type=float, help="seconds after start to send alert on")
    ap.add_argument("--alert-off", type=float, help="seconds after start to send alert off")
    ap.add_argument("--no-reset", action="store_true", help="do not reset the boards at start")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    ports = {"tag": args.tag, "anchor0": args.anchor}
    fds = {name: open_port(path) for name, path in ports.items()}
    t0 = time.monotonic()

    def stamp():
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return f"{now}  +{time.monotonic() - t0:7.3f}s"

    logs = {name: open(os.path.join(args.out, f"{name}.log"), "w", encoding="utf-8") for name in ports}
    cmdlog = open(os.path.join(args.out, "commands.log"), "w", encoding="utf-8")
    for name, path in ports.items():
        logs[name].write(f"# port {path} @115200, capture started {stamp()}\n")

    if not args.no_reset:  # RTS drives EN: pulse it so the boot lines (chip, UWB init) are captured
        for fd in fds.values():
            fcntl.ioctl(fd, termios.TIOCMBIS, struct.pack("I", termios.TIOCM_RTS))
        time.sleep(0.15)
        for fd in fds.values():
            fcntl.ioctl(fd, termios.TIOCMBIC, struct.pack("I", termios.TIOCM_RTS))

    schedule = []
    if args.alert_on is not None:
        schedule.append((args.alert_on, "CMD 101 0 alert 1"))
    if args.alert_off is not None:
        schedule.append((args.alert_off, "CMD 102 0 alert 0"))
    schedule.sort()

    bufs = {name: b"" for name in ports}
    while time.monotonic() - t0 < args.seconds:
        if schedule and time.monotonic() - t0 >= schedule[0][0]:
            _, cmd = schedule.pop(0)
            os.write(fds["anchor0"], (cmd + "\n").encode())
            cmdlog.write(f"{stamp()}  -> anchor0: {cmd}\n")
            cmdlog.flush()
        ready = select.select(list(fds.values()), [], [], 0.05)[0]
        for name, fd in fds.items():
            if fd not in ready:
                continue
            try:
                bufs[name] += os.read(fd, 4096)
            except BlockingIOError:
                continue
            while b"\n" in bufs[name]:
                line, bufs[name] = bufs[name].split(b"\n", 1)
                logs[name].write(f"{stamp()}  {line.decode('utf-8', errors='replace').rstrip()}\n")

    # A line still in the buffer at the end is incomplete; mark it instead of saving it as data.
    for name in ports:
        if bufs[name]:
            logs[name].write(f"# incomplete last line dropped ({len(bufs[name])} bytes)\n")
        logs[name].write(f"# capture ended {stamp()}\n")
        logs[name].close()
        os.close(fds[name])
    cmdlog.close()


if __name__ == "__main__":
    main()
