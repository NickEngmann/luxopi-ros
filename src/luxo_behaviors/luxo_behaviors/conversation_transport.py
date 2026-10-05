"""Bounded local text-service transport, independent of ROS and audio devices."""

from collections import deque
import json
import queue
import os
import socket
import signal
import subprocess
import threading
import time
import uuid


class ConversationClient:
    """Own one reusable subprocess; a timeout tears down its stale transaction."""

    def __init__(self, command, cwd=None, timeout=15.0):
        if not command or timeout <= 0:
            raise ValueError("A command and positive timeout are required")
        self.command = list(command)
        self.cwd = cwd
        self.timeout = timeout
        self.diagnostics = deque(maxlen=32)
        self._process = None
        self._results = queue.Queue(maxsize=16)
        self._lock = threading.Lock()

    def _read_output(self, process, results):
        try:
            for line in process.stdout:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        results.put_nowait(item)
                except (ValueError, queue.Full):
                    self.diagnostics.append("Discarded invalid or surplus service output")
        except (OSError, ValueError):
            pass  # Process shutdown closes its owned pipes.

    def _read_errors(self, process):
        try:
            for line in process.stderr:
                self.diagnostics.append(line.strip()[:1000])
        except (OSError, ValueError):
            pass

    def _start(self):
        if self._process is not None and self._process.poll() is None:
            return
        self.close()
        self._results = queue.Queue(maxsize=16)
        self._process = subprocess.Popen(
            self.command, cwd=self.cwd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            start_new_session=True,
        )
        threading.Thread(target=self._read_output, args=(self._process, self._results), daemon=True).start()
        threading.Thread(target=self._read_errors, args=(self._process,), daemon=True).start()

    def request(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("text must contain 1–2000 characters")
        return self._request({"text": text})

    def request_audio(self, name):
        from luxo_behaviors.audio_input import validate_audio_name
        return self._request({"audio_file": validate_audio_name(name)})

    def _request(self, payload):
        with self._lock:
            self._start()
            process = self._process
            request_id = uuid.uuid4().hex
            try:
                process.stdin.write(json.dumps({"id": request_id, **payload}) + "\n")
                process.stdin.flush()
                deadline = time.monotonic() + self.timeout
                while time.monotonic() < deadline:
                    try:
                        result = self._results.get(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
                    except queue.Empty:
                        if process.poll() is not None:
                            raise RuntimeError("Local conversation service exited")
                        continue
                    if result.get("id") != request_id:
                        continue
                    if result.get("error"):
                        raise RuntimeError(result["error"])
                    if not isinstance(result.get("response"), str):
                        raise RuntimeError("Service returned no response text")
                    return result
                raise TimeoutError("Local conversation service timed out")
            except (BrokenPipeError, OSError, RuntimeError, TimeoutError, ValueError):
                self.close()
                raise

    def close(self):
        process, self._process = self._process, None
        if process is not None:
            if process.poll() is None:
                self._signal_group(process, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._signal_group(process, signal.SIGKILL)
                    process.wait(timeout=2)
            # A service can exit while an inference child survives it. Never
            # leave a model server holding the port after a timed-out request.
            self._signal_group(process, signal.SIGKILL)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe:
                    pipe.close()

    @staticmethod
    def _signal_group(process, signum):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass


class SimulatedConversation:
    """Explicit mock backend; never presented as a language model result."""

    from luxo_behaviors.simulator_protocol import ANIMATION_NAMES
    ANIMATIONS = frozenset(ANIMATION_NAMES)

    def request(self, text):
        text = text.strip()
        candidate = text.lower().strip(" .!?")
        if candidate.startswith("please "):
            candidate = candidate[7:]
        candidate = candidate.replace(" ", "_")
        animation = candidate if candidate in self.ANIMATIONS else None
        return {
            "text": text, "response": f"Simulator heard: {text}",
            "animation": animation, "source": "simulation", "audio_path": None,
        }

    def close(self):
        pass


class LocalEventReceiver:
    """Same-user Unix datagrams; never overwrite another process's socket."""

    def __init__(self, path):
        self.path = path
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            self.socket.bind(path)
            os.chmod(path, 0o600)
            self._inode = os.stat(path).st_ino
            self.socket.settimeout(0.1)
        except BaseException:
            self.socket.close()
            raise

    def read(self):
        try:
            raw = self.socket.recv(8193)
            if len(raw) > 8192:
                return None
            result = json.loads(raw)
            return result if isinstance(result, dict) else None
        except (socket.timeout, ValueError, UnicodeError):
            return None

    def close(self):
        self.socket.close()
        try:
            if os.stat(self.path).st_ino == self._inode:
                os.unlink(self.path)
        except FileNotFoundError:
            pass
