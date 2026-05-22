"""WASAPI loopback audio capture from the active output device."""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path
from typing import Optional

import pyaudiowpatch as pyaudio

import config

CHUNK = 1024


class AudioCapture:
    def __init__(self) -> None:
        self._frames: list[bytes] = []
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._loopback_device: Optional[dict] = None
        self._pa: Optional[pyaudio.PyAudio] = None
        self._sample_rate: int = 0
        self._channels: int = 0
        self._stream_closed = threading.Event()

    def _find_loopback_device(self, pa: pyaudio.PyAudio) -> Optional[dict]:
        """Return device info dict for the loopback of the current default WASAPI output."""
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("ERROR: WASAPI not available on this system.")
            return None

        default_out_idx = wasapi_info["defaultOutputDevice"]
        default_out = pa.get_device_info_by_index(default_out_idx)
        default_name = default_out["name"]

        # Find the loopback device that corresponds to the default output
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            if not dev.get("isLoopbackDevice"):
                continue
            # Match by base name (loopback name is "<output name> [Loopback]")
            if default_name in dev["name"]:
                print(f"Using loopback device: {dev['name']} (index {i})")
                return dev

        # Fallback: return any loopback device
        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice") and dev["maxInputChannels"] > 0:
                print(f"Using fallback loopback device: {dev['name']} (index {i})")
                return dev

        return None

    def start(self) -> bool:
        """Begin recording. Returns True if started successfully."""
        self._pa = pyaudio.PyAudio()
        self._loopback_device = self._find_loopback_device(self._pa)

        if self._loopback_device is None:
            print(
                "ERROR: No WASAPI loopback device found.\n"
                "Try installing VB-CABLE (https://vb-audio.com/Cable/) and setting it as default output."
            )
            self._pa.terminate()
            self._pa = None
            return False

        self._sample_rate = int(self._loopback_device["defaultSampleRate"])
        self._channels = self._loopback_device["maxInputChannels"]
        self._frames = []
        self._recording = True
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()
        print("Audio capture started.")
        return True

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    def frames_since(self, since_index: int) -> tuple[list[bytes], int]:
        """Return frames recorded after since_index, and the new end index."""
        frames = self._frames[since_index:]
        return frames, since_index + len(frames)

    def _record(self) -> None:
        dev = self._loopback_device
        sample_rate = int(dev["defaultSampleRate"])
        channels = dev["maxInputChannels"]
        dev_index = dev["index"]

        stream = None
        try:
            stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=dev_index,
                frames_per_buffer=CHUNK,
            )
            while self._recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                self._frames.append(data)
        except Exception as exc:
            print(f"ERROR during audio capture: {exc}")
            self._recording = False
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            self._stream_closed.set()

    def stop(self, output_path: str) -> Optional[str]:
        """Stop recording, save WAV to output_path, return path on success."""
        self._recording = False
        # WASAPI loopback blocks in stream.read() when no audio is playing (device idles).
        # If the stream doesn't close within the timeout, skip _pa.terminate() entirely --
        # calling it while stream.read() is blocked causes a native crash with no traceback.
        # The record thread is a daemon; Python process exit will clean up the device.
        stream_closed = self._stream_closed.wait(timeout=5)
        if self._thread:
            self._thread.join(timeout=3)

        if stream_closed and self._pa:
            try:
                self._pa.terminate()
            except Exception as exc:
                print(f"WARNING: PyAudio terminate error: {exc}")
        self._pa = None

        if not self._frames:
            print("No audio data captured.")
            return None

        dev = self._loopback_device
        sample_rate = int(dev["defaultSampleRate"])
        channels = dev["maxInputChannels"]

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # paInt16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(b"".join(self._frames))

        print(f"Audio saved: {output_path}")
        return output_path
