"""Text-to-Speech — converts text to audio using multiple backends.

Supports:
- edge-tts (default, high quality, requires internet)
- espeak-ng (fallback, offline, lower quality)
"""
from __future__ import annotations

import asyncio
import io
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger

from ..core.errors import VoiceError


class BaseTTS(ABC):
    """Abstract base for text-to-speech engines."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert text to audio bytes (WAV format)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        ...


class EdgeTTS(BaseTTS):
    """Microsoft Edge TTS — high quality neural voices (requires internet)."""

    def __init__(self, voice: str = "en-US-AriaNeural", rate: str = "+0%", volume: str = "+0%") -> None:
        self._voice = voice
        self._rate = rate
        self._volume = volume
        logger.debug(f"EdgeTTS initialized (voice={voice})")

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio using edge-tts."""
        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text, self._voice, rate=self._rate, volume=self._volume
            )

            # Collect audio data
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if not audio_data:
                raise VoiceError("Edge TTS returned empty audio.")

            # edge-tts returns MP3, convert to WAV using ffmpeg if available
            wav_data = await self._mp3_to_wav(audio_data)
            logger.debug(f"EdgeTTS: synthesized {len(text)} chars → {len(wav_data)} bytes WAV")
            return wav_data

        except ImportError:
            raise VoiceError(
                "edge-tts not installed.",
                details="Install with: pip install edge-tts",
            )
        except VoiceError:
            raise
        except Exception as e:
            raise VoiceError(f"Edge TTS failed: {e}")

    async def _mp3_to_wav(self, mp3_data: bytes) -> bytes:
        """Convert MP3 bytes to WAV using ffmpeg."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as mp3_tmp:
                mp3_tmp.write(mp3_data)
                mp3_tmp.flush()

                wav_path = mp3_tmp.name.replace(".mp3", ".wav")

                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-i", mp3_tmp.name, "-ar", "16000", "-ac", "1",
                    "-f", "wav", wav_path, "-y",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()

                if proc.returncode == 0 and Path(wav_path).exists():
                    wav_data = Path(wav_path).read_bytes()
                    Path(wav_path).unlink(missing_ok=True)
                    return wav_data
                else:
                    # Return raw MP3 if ffmpeg conversion fails
                    logger.warning("ffmpeg MP3→WAV conversion failed, returning raw MP3")
                    return mp3_data
        except FileNotFoundError:
            logger.warning("ffmpeg not found, returning raw MP3 data")
            return mp3_data

    async def close(self) -> None:
        pass


class EspeakTTS(BaseTTS):
    """espeak-ng TTS — offline, lower quality, always available."""

    def __init__(self, voice: str = "en", speed: int = 160, amplitude: int = 80) -> None:
        self._voice = voice
        self._speed = speed
        self._amplitude = amplitude
        # Verify espeak-ng is available
        try:
            subprocess.run(
                ["espeak-ng", "--version"],
                capture_output=True, timeout=5,
            )
            logger.debug(f"EspeakTTS initialized (voice={voice}, speed={speed})")
        except FileNotFoundError:
            raise VoiceError(
                "espeak-ng not found.",
                details="Install with: apt install espeak-ng",
            )

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV using espeak-ng."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                proc = await asyncio.create_subprocess_exec(
                    "espeak-ng",
                    "-v", self._voice,
                    "-s", str(self._speed),
                    "-a", str(self._amplitude),
                    "-w", tmp.name,
                    text,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()

                if proc.returncode == 0 and Path(tmp.name).exists():
                    audio_data = Path(tmp.name).read_bytes()
                    logger.debug(f"EspeakTTS: synthesized {len(text)} chars → {len(audio_data)} bytes")
                    return audio_data
                else:
                    raise VoiceError("espeak-ng synthesis failed.")

        except VoiceError:
            raise
        except Exception as e:
            raise VoiceError(f"espeak-ng TTS failed: {e}")

    async def close(self) -> None:
        pass


def create_tts(engine: str = "edge", **kwargs) -> BaseTTS:
    """Factory for TTS engines."""
    engines = {
        "edge": EdgeTTS,
        "espeak": EspeakTTS,
    }
    cls = engines.get(engine)
    if not cls:
        raise VoiceError(
            f"Unknown TTS engine: '{engine}'",
            details=f"Available: {', '.join(engines.keys())}",
        )
    return cls(**kwargs)
