"""Microphone input — captures audio from system microphone.

Supports both PyAudio and sounddevice backends.
"""
from __future__ import annotations

import asyncio
import io
import tempfile
import threading
import wave
from typing import Callable

from loguru import logger

from ..core.errors import VoiceError


class MicrophoneManager:
    """Manages microphone capture for voice input."""

    def __init__(self, device_index: int | None = None, sample_rate: int = 16000) -> None:
        self._device_index = device_index
        self._sample_rate = sample_rate
        self._is_recording = False
        self._audio_chunks: list[bytes] = []
        self._backend = None
        self._stream = None

        # Detect best available backend
        self._detect_backend()

    def _detect_backend(self) -> None:
        """Detect the best available audio backend."""
        try:
            import pyaudio
            self._pyaudio = pyaudio
            self._backend = "pyaudio"
            logger.debug("Microphone: using PyAudio backend")
            return
        except ImportError:
            pass

        try:
            import sounddevice as sd
            self._sounddevice = sd
            self._backend = "sounddevice"
            logger.debug("Microphone: using sounddevice backend")
            return
        except ImportError:
            pass

        raise VoiceError(
            "No audio backend available.",
            details="Install PyAudio or sounddevice for microphone input.",
        )

    def list_devices(self) -> list[dict]:
        """List available audio input devices."""
        devices = []
        try:
            if self._backend == "pyaudio":
                pa = self._pyaudio.PyAudio()
                for i in range(pa.get_device_count()):
                    info = pa.get_device_info_by_index(i)
                    if info["maxInputChannels"] > 0:
                        devices.append({
                            "index": i,
                            "name": info["name"],
                            "channels": info["maxInputChannels"],
                            "sample_rate": int(info["defaultSampleRate"]),
                        })
                pa.terminate()
            elif self._backend == "sounddevice":
                for i, d in enumerate(self._sounddevice.query_devices()):
                    if d["max_input_channels"] > 0:
                        devices.append({
                            "index": i,
                            "name": d["name"],
                            "channels": d["max_input_channels"],
                            "sample_rate": int(d["default_samplerate"]),
                        })
        except Exception as e:
            logger.warning(f"Failed to list audio devices: {e}")

        return devices

    async def record_chunk(self, duration: float = 5.0) -> bytes:
        """Record audio for a fixed duration and return raw PCM bytes.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Raw 16-bit PCM audio bytes.
        """
        if self._backend == "pyaudio":
            return await self._record_pyaudio(duration)
        elif self._backend == "sounddevice":
            return await self._record_sounddevice(duration)
        raise VoiceError("No audio backend available.")

    async def _record_pyaudio(self, duration: float) -> bytes:
        """Record using PyAudio."""
        pa = self._pyaudio.PyAudio()
        audio_data = io.BytesIO()
        sample_width = 2  # 16-bit
        channels = 1

        try:
            stream = pa.open(
                format=self._pyaudio.paInt16,
                channels=channels,
                rate=self._sample_rate,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=1024,
            )

            loop = asyncio.get_event_loop()
            frames = []
            total_frames = int(self._sample_rate * duration / 1024)

            for _ in range(total_frames):
                data = await loop.run_in_executor(None, stream.read, 1024)
                frames.append(data)

            stream.stop_stream()
            stream.close()

            raw_audio = b"".join(frames)
            logger.debug(f"Recorded {duration}s audio ({len(raw_audio)} bytes)")
            return raw_audio

        except Exception as e:
            raise VoiceError(f"Microphone recording failed: {e}")
        finally:
            pa.terminate()

    async def _record_sounddevice(self, duration: float) -> bytes:
        """Record using sounddevice."""
        import numpy as np

        loop = asyncio.get_event_loop()
        samplerate = self._sample_rate
        channels = 1

        recording = await loop.run_in_executor(
            None,
            lambda: self._sounddevice.rec(
                int(duration * samplerate),
                samplerate=samplerate,
                channels=channels,
                dtype="int16",
                device=self._device_index,
            ),
        )

        # Convert numpy array to bytes
        raw_audio = recording.tobytes()
        logger.debug(f"Recorded {duration}s audio ({len(raw_audio)} bytes)")
        return raw_audio

    def start_streaming(self, callback: Callable[[bytes], None], chunk_size: int = 1024) -> None:
        """Start streaming microphone audio to a callback (non-blocking)."""
        if self._is_recording:
            return

        self._is_recording = True
        self._audio_chunks = []

        def _stream_worker():
            try:
                if self._backend == "pyaudio":
                    pa = self._pyaudio.PyAudio()
                    stream = pa.open(
                        format=self._pyaudio.paInt16,
                        channels=1,
                        rate=self._sample_rate,
                        input=True,
                        input_device_index=self._device_index,
                        frames_per_buffer=chunk_size,
                    )

                    while self._is_recording:
                        data = stream.read(chunk_size, exception_on_overflow=False)
                        callback(data)

                    stream.stop_stream()
                    stream.close()
                    pa.terminate()

                elif self._backend == "sounddevice":
                    def audio_callback(indata, frames, time, status):
                        if self._is_recording:
                            callback(indata.tobytes())

                    with self._sounddevice.InputStream(
                        samplerate=self._sample_rate,
                        channels=1,
                        dtype="int16",
                        callback=audio_callback,
                        device=self._device_index,
                        blocksize=chunk_size,
                    ):
                        while self._is_recording:
                            self._sounddevice.sleep(100)

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                self._is_recording = False

        thread = threading.Thread(target=_stream_worker, daemon=True)
        thread.start()

    def stop_streaming(self) -> None:
        """Stop streaming microphone audio."""
        self._is_recording = False

    @property
    def is_recording(self) -> bool:
        return self._is_recording
