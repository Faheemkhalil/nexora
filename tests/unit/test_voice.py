"""Unit tests for the voice module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestVoiceState:
    """Test VoiceState enum."""

    def test_voice_states_exist(self):
        from app.voice import VoiceState
        assert VoiceState.IDLE.value == "idle"
        assert VoiceState.LISTENING.value == "listening"
        assert VoiceState.THINKING.value == "thinking"
        assert VoiceState.SPEAKING.value == "speaking"
        assert VoiceState.WORKING.value == "working"
        assert VoiceState.ERROR.value == "error"


class TestVoiceManager:
    """Test VoiceManager initialization and state management."""

    def test_voice_manager_init_no_voice(self):
        """VoiceManager should initialize even if engines fail."""
        from app.voice import VoiceManager, VoiceState
        from app.core.errors import VoiceError
        with patch("app.voice.voice_manager.create_stt", side_effect=VoiceError("fail")):
            with patch("app.voice.voice_manager.create_tts", side_effect=VoiceError("fail")):
                with patch("app.voice.voice_manager.MicrophoneManager", side_effect=VoiceError("fail")):
                    vm = VoiceManager()
                    assert vm.state == VoiceState.IDLE
                    assert vm.available["stt"] is False
                    assert vm.available["tts"] is False
                    assert vm.available["microphone"] is False

    def test_voice_manager_state_callbacks(self):
        """State callbacks should be called on state change."""
        from app.voice import VoiceManager, VoiceState
        from app.core.errors import VoiceError
        with patch("app.voice.voice_manager.create_stt", side_effect=VoiceError("fail")):
            with patch("app.voice.voice_manager.create_tts", side_effect=VoiceError("fail")):
                with patch("app.voice.voice_manager.MicrophoneManager", side_effect=VoiceError("fail")):
                    vm = VoiceManager()
                    callback = MagicMock()
                    vm.on_state_change(callback)

                    vm._set_state(VoiceState.LISTENING)
                    callback.assert_called_with(VoiceState.LISTENING)

    def test_voice_manager_close(self):
        """Close should set state to IDLE."""
        from app.voice import VoiceManager, VoiceState
        from app.core.errors import VoiceError
        with patch("app.voice.voice_manager.create_stt", side_effect=VoiceError("fail")):
            with patch("app.voice.voice_manager.create_tts", side_effect=VoiceError("fail")):
                with patch("app.voice.voice_manager.MicrophoneManager", side_effect=VoiceError("fail")):
                    vm = VoiceManager()
                    vm._set_state(VoiceState.LISTENING)
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(vm.close())
                    loop.close()
                    assert vm.state == VoiceState.IDLE


class TestSTT:
    """Test STT factory."""

    def test_create_google_stt(self):
        from app.voice.stt import create_stt
        stt = create_stt("google", language="en-US")
        assert stt is not None

    def test_create_unknown_stt_raises(self):
        from app.voice.stt import create_stt
        from app.core.errors import VoiceError
        with pytest.raises(VoiceError):
            create_stt("nonexistent")


class TestTTS:
    """Test TTS factory."""

    @pytest.mark.skipif(
        not __import__('shutil').which('espeak-ng'),
        reason='espeak-ng binary not installed'
    )
    def test_create_espeak_tts(self):
        from app.voice.tts import create_tts
        tts = create_tts("espeak", voice="en")
        assert tts is not None

    def test_create_unknown_tts_raises(self):
        from app.voice.tts import create_tts
        from app.core.errors import VoiceError
        with pytest.raises(VoiceError):
            create_tts("nonexistent")


class TestVoiceConfig:
    """Test voice settings in config."""

    def test_voice_settings_defaults(self):
        from app.core.config import settings
        assert settings.voice.enabled is True
        assert settings.voice.stt_engine == "google"
        assert settings.voice.tts_engine == "edge"
        assert settings.voice.language == "en-US"
        assert settings.voice.push_to_talk is True
        assert settings.voice.volume == 1.0
