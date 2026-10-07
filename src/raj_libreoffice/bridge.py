from __future__ import annotations

import atexit
import json
import os
import queue
import signal
import subprocess
import threading
from pathlib import Path

from .config import Config


class OfficeError(RuntimeError):
    pass


class Bridge:
    """Serialize UNO access in a dedicated, ABI-compatible Python process.

    A timed-out worker is killed. Handles are invalid after restart. Calls are
    never automatically replayed because a write may already have taken effect.
    """

    def __init__(self, config: Config):
        self.config = config
        self.process = None
        self.lock = threading.RLock()
        self.sequence = 0
        self.responses = queue.Queue()
        atexit.register(self.close)

    def _start(self):
        worker = str(Path(__file__).with_name("worker.py"))
        self.process = subprocess.Popen(
            [self.config.uno_python, "-u", worker],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=None, text=True, encoding="utf-8", bufsize=1,
            start_new_session=os.name == "posix",
        )
        self.responses = queue.Queue()
        process, responses = self.process, self.responses

        def reader():
            try:
                for line in process.stdout:
                    responses.put(line)
            finally:
                responses.put(None)

        threading.Thread(target=reader, daemon=True).start()

    def call(self, operation: str, **arguments):
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self._start()
            self.sequence += 1
            request = {"id": self.sequence, "operation": operation,
                       "arguments": arguments, "config": self.config.wire()}
            try:
                self.process.stdin.write(json.dumps(request, allow_nan=False) + "\n")
                self.process.stdin.flush()
                line = self.responses.get(timeout=self.config.timeout)
            except queue.Empty as error:
                self.close()
                raise OfficeError(
                    "LibreOffice timed out; worker stopped. Reopen documents. "
                    "A write may have completed; inspect files before retrying."
                ) from error
            except (BrokenPipeError, OSError) as error:
                self.close()
                raise OfficeError("UNO worker stopped; run raj-libreoffice doctor") from error
            if line is None:
                self.close()
                raise OfficeError("UNO worker exited; check PyUNO interpreter and stderr")
            response = json.loads(line)
            if response.get("id") != request["id"]:
                self.close()
                raise OfficeError("UNO worker response sequence mismatch")
            if "error" in response:
                raise OfficeError(f"{response['error']['type']}: {response['error']['message']}")
            return response["result"]

    def close(self):
        with self.lock:
            process, self.process = self.process, None
            if process is not None:
                if process.stdin:
                    process.stdin.close()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=3)
                if process.stdout:
                    process.stdout.close()

