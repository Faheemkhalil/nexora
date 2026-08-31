"""Voice pipeline manager — orchestrates microphone, STT, TTS, and voice states.

States:
    IDLE → LISTENING → THINKING → SPEAKING → IDLE
    Any state → ERROR → IDLE
"""
from __future__ import annotations

import asyncio
import enum
import time
from typing import Any, Callable

from loguru import logger

from ..core.errors import VoiceError
from .microphone import MicrophoneManager
from .stt import BaseSTT, create_stt
from .tts import BaseTTS, create_tts


class VoiceState(str, enum.Enum):
    """Voice pipeline states visible in the 3D UI."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WORKING = "working"
    ERROR = "error"


class VoiceManager:
    """Manages the full voice pipeline: microphone → STT → AI → TTS → speaker."""

    def __init__(
        self,
        stt_engine: str = "google",
        tts_engine: str = "edge",
        tts_voice: str = "en-US-AriaNeural",
        language: str = "en-US",
        microphone_device: int | None = None,
    ) -> None:
        self._state = VoiceState.IDLE
        self._stt: BaseSTT | None = None
        self._tts: BaseTTS | None = None
        self._microphone: MicrophoneManager | None = None
        self._language = language
        self._tts_voice = tts_voice
        self._stt_engine = stt_engine
        self._tts_engine = tts_engine
        self._mic_device = microphone_device

        # Event callbacks
        self._state_callbacks: list[Callable[[VoiceState], None]] = []
        self._transcript_callbacks: list[Callable[[str], None]] = []
        self._audio_callbacks: list[Callable[[bytes], None]] = []

        # Conversation context for AI integration
        self._on_user_message: Callable | None = None

        self._initialize_engines()

    def _initialize_engines(self) -> None:
        """Initialize STT, TTS, and microphone engines."""
        try:
            self._stt = create_stt(self._stt_engine, language=self._language)
        except VoiceError as e:
            logger.warning(f"STT initialization failed: {e}")

        try:
            self._tts = create_tts(self._tts_engine, voice=self._tts_voice)
        except VoiceError as e:
            logger.warning(f"TTS initialization failed: {e}")

        try:
            self._microphone = MicrophoneManager(
                device_index=self._mic_device,
                sample_rate=16000,
            )
        except VoiceError as e:
            logger.warning(f"Microphone initialization failed: {e}")

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def available(self) -> dict[str, bool]:
        """Check which voice components are available."""
        return {
            "microphone": self._microphone is not None,
            "stt": self._stt is not None,
            "tts": self._tts is not None,
            "pipeline": all([self._microphone, self._stt, self._tts]),
        }

    def on_state_change(self, callback: Callable[[VoiceState], None]) -> None:
        """Register a callback for voice state changes."""
        self._state_callbacks.append(callback)

    def on_transcript(self, callback: Callable[[str], None]) -> None:
        """Register a callback for transcription results."""
        self._transcript_callbacks.append(callback)

    def on_audio(self, callback: Callable[[bytes], None]) -> None:
        """Register a callback for TTS audio output."""
        self._audio_callbacks.append(callback)

    def set_message_handler(self, handler: Callable) -> None:
        """Set the handler for user voice messages (connects to chat/AI)."""
        self._on_user_message = handler

    def _set_state(self, state: VoiceState) -> None:
        """Update voice state and notify callbacks."""
        self._state = state
        logger.debug(f"Voice state → {state.value}")
        for cb in self._state_callbacks:
            try:
                cb(state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def list_devices(self) -> list[dict]:
        """List available microphone devices."""
        if self._microphone:
            return self._microphone.list_devices()
        return []

    async def start_listening(self, duration: float = 5.0) -> str:
        """Record audio, transcribe with STT, return text.

        Args:
            duration: How long to record (seconds).

        Returns:
            Transcribed text, or empty string if silence/noise.
        """
        if not self._microphone:
            raise VoiceError("Microphone not available.")
        if not self._stt:
            raise VoiceError("STT engine not available.")

        self._set_state(VoiceState.LISTENING)

        try:
            # Record audio
            audio_data = await self._microphone.record_chunk(duration)

            if not audio_data or len(audio_data) < 1000:
                self._set_state(VoiceState.IDLE)
                return ""

            # Transcribe
            self._set_state(VoiceState.THINKING)
            text = await self._stt.transcribe(audio_data)

            if text:
                logger.info(f"Voice transcript: '{text}'")
                for cb in self._transcript_callbacks:
                    try:
                        cb(text)
                    except Exception as e:
                        logger.error(f"Transcript callback error: {e}")
            else:
                self._set_state(VoiceState.IDLE)

            return text

        except VoiceError:
            self._set_state(VoiceState.ERROR)
            raise
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            raise VoiceError(f"Listening failed: {e}")

    async def speak(self, text: str) -> bytes:
        """Convert text to speech and return audio bytes.

        Args:
            text: Text to speak.

        Returns:
            WAV audio bytes.
        """
        if not self._tts:
            raise VoiceError("TTS engine not available.")

        self._set_state(VoiceState.SPEAKING)

        try:
            audio_data = await self._tts.synthesize(text)

            for cb in self._audio_callbacks:
                try:
                    cb(audio_data)
                except Exception as e:
                    logger.error(f"Audio callback error: {e}")

            self._set_state(VoiceState.IDLE)
            return audio_data

        except VoiceError:
            self._set_state(VoiceState.ERROR)
            raise
        except Exception as e:
            self._set_state(VoiceState.ERROR)
            raise VoiceError(f"Speech synthesis failed: {e}")

    async def voice_chat(self, duration: float = 5.0) -> dict[str, Any]:
        """Full voice chat cycle: listen → transcribe → AI → speak.

        Returns:
            Dict with transcript, response, and audio data.
        """
        # Listen
        transcript = await self.start_listening(duration)
        if not transcript:
            return {"transcript": "", "response": "", "audio": None}

        # Think (AI processing happens externally via callback)
        self._set_state(VoiceState.THINKING)

        # The actual AI call happens through the registered message handler
        # For now, return the transcript for the caller to process
        return {"transcript": transcript, "response": "", "audio": None}

    async def reconfigure(
        self,
        stt_engine: str | None = None,
        tts_engine: str | None = None,
        tts_voice: str | None = None,
        language: str | None = None,
        microphone_device: int | None = None,
    ) -> None:
        """Reconfigure voice engines at runtime."""
        if stt_engine:
            self._stt_engine = stt_engine
        if tts_engine:
            self._tts_engine = tts_engine
        if tts_voice:
            self._tts_voice = tts_voice
        if language:
            self._language = language
        if microphone_device is not None:
            self._mic_device = microphone_device

        # Close existing engines
        await self.close()

        # Re-initialize
        self._initialize_engines()
        logger.info("Voice pipeline reconfigured.")

    async def close(self) -> None:
        """Clean up all voice resources."""
        self._set_state(VoiceState.IDLE)

        if self._stt:
            await self._stt.close()
            self._stt = None

        if self._tts:
            await self._tts.close()
            self._tts = None

        if self._microphone:
            self._microphone.stop_streaming()
            self._microphone = None

        logger.debug("Voice pipeline closed.")
