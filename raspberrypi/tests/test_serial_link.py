import fcntl
import os
from pathlib import Path
import pty
import select
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fire_tag_receiver import SerialLink


class SerialLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.master, self.slave = pty.openpty()
        self.port = Path(self.tmp.name) / "anchor"
        self.port.symlink_to(os.ttyname(self.slave))
        real_ioctl = fcntl.ioctl
        self.ioctl = patch("fcntl.ioctl", side_effect=lambda fd, cmd, *args:
                           0 if cmd == termios.TIOCMBIC else real_ioctl(fd, cmd, *args))
        self.ioctl.start()
        self.no_serial = patch.dict(sys.modules, {"serial": None})
        self.no_serial.start()
        self.link = SerialLink(str(self.port), 115200)

    def tearDown(self):
        if hasattr(self.link, "close"):
            self.link.close()
        elif self.link.fd is not None:
            os.close(self.link.fd)
        for fd in (self.master, self.slave):
            try: os.close(fd)
            except OSError: pass
        self.no_serial.stop()
        self.ioctl.stop()
        self.tmp.cleanup()

    def test_partial_input_and_idle_ticks_preserve_complete_lines(self):
        lines = self.link.lines()
        os.write(self.master, b'{"anchor":')
        self.assertIsNone(next(lines))
        os.write(self.master, b'0}\n')
        self.assertEqual(next(lines), '{"anchor":0}')
        self.link.write("CMD 1 0 ping 0")
        self.assertTrue(select.select([self.master], [], [], 1)[0])
        self.assertEqual(os.read(self.master, 100), b"\nCMD 1 0 ping 0\n")

    def test_short_writes_do_not_truncate_commands(self):
        real_write = os.write
        with patch("os.write", side_effect=lambda fd, data: real_write(fd, data[:2])):
            self.link.write("CMD 12 1 range 2")
        self.assertTrue(select.select([self.master], [], [], 1)[0])
        self.assertEqual(os.read(self.master, 100), b"\nCMD 12 1 range 2\n")

    def test_partial_failed_write_is_separated_from_the_next_connection(self):
        real_write = os.write
        sent = []
        def interrupted(fd, data):
            if not sent:
                sent.append(real_write(fd, data[:18])); return sent[-1]
            raise OSError(5, "USB interrupted")
        with patch("os.write", side_effect=interrupted):
            self.assertFalse(self.link.write("CMD 61441 0 alert 1"))
        self.assertTrue(self.link.last_write_partial)
        self.link.retry_at = 0
        next(self.link.lines())
        self.assertTrue(self.link.write("CMD 61442 0 alert 1"))
        self.assertFalse(self.link.last_write_partial)
        wire = os.read(self.master, 200)
        self.assertIn(b"\nCMD 61442 0 alert 1\n", wire)

    def test_unplugged_port_yields_idle_and_reconnects_to_replacement_device(self):
        lines = self.link.lines()
        os.close(self.master)
        try:
            value = next(lines)
        except OSError as e:
            self.fail(f"Unplugging the port escaped to the receiver: {e}")
        self.assertIsNone(value)
        self.master, slave = pty.openpty()
        self.port.unlink()
        self.port.symlink_to(os.ttyname(slave))
        os.close(self.slave)
        self.slave = slave
        deadline = time.monotonic() + 3
        recovered = False
        while time.monotonic() < deadline:
            self.link.write("CMD 2 0 ping 0")
            next(lines)
            if select.select([self.master], [], [], 0)[0]:
                data = os.read(self.master, 100)
                if b"CMD 2 0 ping 0\n" in data:
                    recovered = True
                    break
        self.assertTrue(recovered, "The replacement port never received a command")

    def test_a_full_output_queue_cannot_block_the_receiver_indefinitely(self):
        while True:
            try: os.write(self.link.fd, b'x' * 8192)
            except BlockingIOError: break
        start = time.monotonic()
        self.assertFalse(self.link.write("CMD 3 0 ping 0"))
        self.assertLess(time.monotonic() - start, 2)
        self.assertIsNotNone(self.link.error)

    def test_termios_configuration_error_closes_the_opened_descriptor(self):
        opened = []
        real_open = os.open
        def track_open(*args):
            fd = real_open(*args); opened.append(fd); return fd
        try:
            with patch("os.open", side_effect=track_open), patch("tty.setraw", side_effect=termios.error(5, "config failed")):
                try:
                    SerialLink(str(self.port), 115200)
                except Exception as e:
                    self.assertIsInstance(e, OSError)
                else:
                    self.fail("Configuration errors must be surfaced")
            with self.assertRaises(OSError): fcntl.fcntl(opened[0], fcntl.F_GETFD)
        finally:
            for fd in opened:
                try: os.close(fd)
                except OSError: pass


if __name__ == "__main__":
    unittest.main()
