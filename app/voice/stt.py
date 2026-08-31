"""Speech-to-Text — converts audio to text using multiple backends.

Supports:
- Google free API (default, requires internet)
- Whisper (optional, local)
"""
from __future__ import annotations

import io
import tempfile
import wave
from abc import ABC, abstractmethod

from loguru import logger

from ..core.errors import VoiceError


class BaseSTT(ABC):
    """Abstract base for speech-to-text engines."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw audio bytes to text."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        ...


class GoogleSTT(BaseSTT):
    """Google free speech recognition (requires internet, no API key)."""

    def __init__(self, language: str = "en-US") -> None:
        self._language = language
        self._recognizer = None
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._sr = sr
            logger.debug(f"GoogleSTT initialized (language={language})")
        except ImportError:
            raise VoiceError(
                "SpeechRecognition not installed.",
                details="Install with: pip install SpeechRecognition",
            )

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio using Google free speech recognition."""
        if not self._recognizer:
            raise VoiceError("STT not initialized.")

        try:
            # Convert raw audio bytes to AudioData
            audio = self._bytes_to_audio_data(audio_data, sample_rate)

            # Use Google free API (no key needed)
            loop = __import__("asyncio").get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: self._recognizer.recognize_google(
                    audio, language=self._language
                ),
            )
            logger.debug(f"STT result: '{text[:100]}...' " if len(str(text)) > 100 else f"STT result: '{text}'")
            return str(text)

        except Exception as e:
            if "Could not understand audio" in str(e) or "Unrecognized audio" in str(e):
                logger.warning("STT: Could not understand audio")
                return ""
            raise VoiceError(
                f"Speech recognition failed: {e}",
                details="Check microphone and try again.",
            )

    def _bytes_to_audio_data(self, audio_data: bytes, sample_rate: int):
        """Convert raw audio bytes to SpeechRecognition AudioData."""
        sr = self._sr

        # Write WAV to temp file then read back
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            with sr.AudioFile(tmp.name) as source:
                audio = self._recognizer.record(source)
            return audio

    async def close(self) -> None:
        self._recognizer = None


class WhisperSTT(BaseSTT):
    """Local Whisper STT (requires openai-whisper package)."""

    def __init__(self, model_name: str = "base") -> None:
        self._model = None
        try:
            import whisper
            self._model = whisper.load_model(model_name)
            logger.debug(f"WhisperSTT initialized (model={model_name})")
        except ImportError:
            raise VoiceError(
                "Whisper not installed.",
                details="Install with: pip install openai-whisper",
            )

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self._model:
            raise VoiceError("Whisper model not loaded.")

        try:
            # Save audio to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                with wave.open(tmp.name, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data)

                loop = __import__("asyncio").get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: self._model.transcribe(tmp.name)
                )
                text = result.get("text", "")
                logger.debug(f"Whisper result: '{text[:100]}'")
                return text

        except Exception as e:
            raise VoiceError(f"Whisper transcription failed: {e}")

    async def close(self) -> None:
        self._model = None


def create_stt(engine: str = "google", **kwargs) -> BaseSTT:
    """Factory for STT engines."""
    engines = {
        "google": GoogleSTT,
        "whisper": WhisperSTT,
    }
    cls = engines.get(engine)
    if not cls:
        raise VoiceError(
            f"Unknown STT engine: '{engine}'",
            details=f"Available: {', '.join(engines.keys())}",
        )
    return cls(**kwargs)
