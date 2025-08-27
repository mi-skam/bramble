"""MPV player controller with IPC socket communication."""

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MPVController:
    """Control MPV player via IPC socket."""

    def __init__(
        self,
        socket_path: str | None = None,
        video_output: str | None = None,
        hardware_decode: str = "auto",
        fullscreen: bool = True,
        test_mode: bool = False,
    ) -> None:
        """Initialize MPV controller.

        Args:
            socket_path: Path to IPC socket. If None, uses temp directory.
            video_output: Video output driver. If None, auto-detects.
            hardware_decode: Hardware decoding mode.
            fullscreen: Start in fullscreen mode.
            test_mode: Use windowed mode for testing.
        """
        self.socket_path = socket_path or str(Path(tempfile.gettempdir()) / "mpv-ipc.sock")
        self.video_output = video_output or self._detect_video_output()
        self.hardware_decode = hardware_decode
        self.fullscreen = fullscreen and not test_mode
        self.test_mode = test_mode
        self.process: subprocess.Popen | None = None
        self.socket: socket.socket | None = None
        self.request_id = 0

    def _detect_video_output(self) -> str:
        """Auto-detect appropriate video output based on platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()

        if ("arm" in machine or "aarch" in machine) and os.path.exists("/dev/dri"):
            logger.info("Detected Raspberry Pi, using DRM output")
            return "drm"

        if system == "darwin":
            logger.info("Detected macOS, using gpu output")
            return "gpu"
        elif system == "linux":
            if os.environ.get("DISPLAY"):
                logger.info("Detected Linux with X11/Wayland, using gpu output")
                return "gpu"
            else:
                logger.info("Detected Linux without display, using drm output")
                return "drm"

        logger.info("Using default gpu output")
        return "gpu"

    def _check_mpv_installed(self) -> bool:
        """Check if MPV is installed."""
        if not shutil.which("mpv"):
            logger.error("MPV is not installed!")
            logger.error("Install MPV:")
            logger.error("  macOS: brew install mpv")
            logger.error("  Ubuntu/Debian: sudo apt-get install mpv")
            logger.error("  Arch: sudo pacman -S mpv")
            logger.error("  Raspberry Pi OS: sudo apt-get install mpv")
            return False
        return True

    def is_running(self) -> bool:
        """Check if MPV process is still running."""
        if self.process is None:
            return False

        poll_result = self.process.poll()
        if poll_result is not None:
            # Process has terminated
            if poll_result == 0:
                logger.info("MPV process exited normally (user quit)")
            else:
                logger.warning(f"MPV process terminated with exit code {poll_result}")
                self._log_mpv_output()
            return False

        return True

    def get_exit_code(self) -> int | None:
        """Get the exit code of the MPV process if it has terminated."""
        if self.process is None:
            return None
        return self.process.poll()

    def _log_mpv_output(self) -> None:
        """Log any available output from MPV process."""
        if self.process and self.process.stdout:
            try:
                # Read any available output
                import select

                ready, _, _ = select.select([self.process.stdout], [], [], 0)
                if ready:
                    output = self.process.stdout.read()
                    if output:
                        logger.warning(f"MPV output: {output.strip()}")
            except Exception as e:
                logger.debug(f"Could not read MPV output: {e}")

    def start(self) -> bool:
        """Start MPV process with IPC socket."""
        if not self._check_mpv_installed():
            return False

        if self.is_running():
            logger.warning("MPV is already running")
            return True

        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        cmd = [
            "mpv",
            f"--input-ipc-server={self.socket_path}",
            f"--vo={self.video_output}",
            f"--hwdec={self.hardware_decode}",
            "--idle=yes",
            "--force-window=yes",
            "--keep-open=always",
            "--image-display-duration=inf",
            "--no-osc",
            "--cursor-autohide=always",
            "--no-config",
            "--quiet",  # Reduce output noise
        ]

        if self.fullscreen:
            cmd.append("--fullscreen")

        if self.video_output == "drm":
            # Use first available connector, preferred mode
            cmd.append("--drm-mode=preferred")

        try:
            logger.info(f"Starting MPV with command: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                universal_newlines=True,
                bufsize=1,  # Line buffered
            )

            # Wait for socket to be created
            for _attempt in range(50):
                if os.path.exists(self.socket_path):
                    break
                if not self.is_running():
                    logger.error("MPV process died during startup")
                    return False
                time.sleep(0.1)
            else:
                logger.error("MPV socket not created after 5 seconds")
                self.stop()
                return False

            return self._connect_socket()

        except Exception as e:
            logger.error(f"Failed to start MPV: {e}")
            return False

    def _connect_socket(self) -> bool:
        """Connect to MPV IPC socket."""
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(self.socket_path)
            self.socket.settimeout(5.0)
            logger.info(f"Connected to MPV socket at {self.socket_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MPV socket: {e}")
            return False

    def _send_command(self, command: list[Any]) -> dict[str, Any] | None:
        """Send command to MPV via IPC socket."""
        # Check if MPV process is still running
        if not self.is_running():
            logger.error("MPV process is not running")
            return None

        if not self.socket and not self._connect_socket():
            return None

        self.request_id += 1
        request = {
            "command": command,
            "request_id": self.request_id,
        }

        # Try the command with retry logic
        max_retries = 2
        for attempt in range(max_retries):
            original_timeout = None
            try:
                msg = json.dumps(request) + "\n"
                if self.socket is not None:
                    self.socket.send(msg.encode("utf-8"))
                else:
                    logger.error("Socket is None when trying to send data")
                    return None

                # Set a shorter timeout for receiving response
                if self.socket is not None:
                    original_timeout = self.socket.gettimeout()
                    self.socket.settimeout(3.0)
                    response_data = self.socket.recv(4096).decode("utf-8")
                    self.socket.settimeout(original_timeout)
                else:
                    logger.error("Socket is None when trying to receive data")
                    return None

                for line in response_data.strip().split("\n"):
                    if line:
                        response: dict[str, Any] = json.loads(line)
                        if response.get("request_id") == self.request_id:
                            if response.get("error") != "success":
                                logger.debug(f"MPV command response: {response.get('error')}")
                            return response

            except TimeoutError:
                logger.warning(f"Timeout waiting for MPV response (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    # Try to reconnect for next attempt
                    self.socket = None
                    if not self._connect_socket():
                        break
                else:
                    logger.error("Final timeout waiting for MPV response")
                    self.socket = None
                    return None
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Socket error (attempt {attempt + 1}/{max_retries}): {e}")
                self.socket = None
                if attempt < max_retries - 1:
                    # Try to reconnect for next attempt
                    if not self._connect_socket():
                        break
                else:
                    logger.error(f"Final socket error: {e}")
                    return None

        return None

    def restart(self) -> bool:
        """Restart MPV process."""
        logger.info("Restarting MPV process...")
        self.stop()
        time.sleep(1.0)
        return self.start()

    def load_file(self, file_path: str, duration: float | None = None) -> bool:
        """Load a media file for playback.

        Args:
            file_path: Path to the media file.
            duration: Duration in seconds for images (None for videos).
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        # Try to restart MPV if it's not running
        if not self.is_running():
            logger.warning("MPV not running, attempting restart...")
            if not self.restart():
                logger.error("Failed to restart MPV")
                return False

        response = self._send_command(["loadfile", file_path, "replace"])
        if not response:
            logger.error("No response from MPV for loadfile command")
            return False
        if response.get("error") != "success":
            logger.error(f"MPV loadfile error: {response.get('error')}")
            return False

        # Start playback (MPV starts paused by default)
        play_response = self._send_command(["set_property", "pause", False])
        if not play_response or play_response.get("error") != "success":
            logger.warning("Failed to start playback, but file loaded")

        # For images, we'll handle timing in the scheduler
        # MPV will keep the image displayed indefinitely

        logger.info(f"Loaded file: {file_path}")
        return True

    def append_to_playlist(self, file_path: str) -> bool:
        """Append a file to the playlist."""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        response = self._send_command(["loadfile", file_path, "append"])
        return response is not None and response.get("error") == "success"

    def play(self) -> bool:
        """Start playback."""
        response = self._send_command(["set_property", "pause", False])
        return response is not None and response.get("error") == "success"

    def pause(self) -> bool:
        """Pause playback."""
        response = self._send_command(["set_property", "pause", True])
        return response is not None and response.get("error") == "success"

    def next(self) -> bool:
        """Skip to next item in playlist."""
        response = self._send_command(["playlist-next"])
        return response is not None and response.get("error") == "success"

    def previous(self) -> bool:
        """Skip to previous item in playlist."""
        response = self._send_command(["playlist-prev"])
        return response is not None and response.get("error") == "success"

    def clear_playlist(self) -> bool:
        """Clear the playlist."""
        response = self._send_command(["playlist-clear"])
        return response is not None and response.get("error") == "success"

    def get_property(self, property_name: str) -> Any:
        """Get a property value from MPV."""
        response = self._send_command(["get_property", property_name])
        if response and response.get("error") == "success":
            return response.get("data")
        return None

    def set_property(self, property_name: str, value: Any) -> bool:
        """Set a property value in MPV."""
        response = self._send_command(["set_property", property_name, value])
        return response is not None and response.get("error") == "success"

    def stop(self) -> None:
        """Stop MPV process and cleanup."""
        if self.socket:
            import contextlib

            with contextlib.suppress(Exception):
                self._send_command(["quit"])
            self.socket.close()
            self.socket = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping MPV: {e}")
            finally:
                self.process = None

        if os.path.exists(self.socket_path):
            import contextlib

            with contextlib.suppress(Exception):
                os.unlink(self.socket_path)

        logger.info("MPV stopped")

    def __enter__(self) -> "MPVController":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.stop()
