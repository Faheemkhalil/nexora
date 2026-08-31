// Voice Controller Component — push-to-talk, voice state, recording indicator

import { IPCClient } from '../lib/ipc';

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working' | 'error';

export class VoiceController {
  private element: HTMLElement;
  private ipc: IPCClient;
  private state: VoiceState = 'idle';
  private isRecording = false;
  private recordTimer: number | null = null;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'voice-controller';
    div.innerHTML = `
      <button class="voice-btn" title="Push to Talk (hold)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
          <line x1="8" y1="19" x2="8" y2="22"/>
          <line x1="16" y1="19" x2="16" y2="22"/>
        </svg>
        <span class="voice-indicator"></span>
      </button>
      <div class="voice-status">
        <span class="voice-state-text">Voice Ready</span>
        <span class="voice-transcript"></span>
      </div>
    `;
    return div;
  }

  private mount(): void {
    const chatHeader = document.querySelector('.chat-header');
    if (chatHeader) {
      chatHeader.appendChild(this.element);
    }
  }

  private setupListeners(): void {
    const btn = this.element.querySelector('.voice-btn') as HTMLButtonElement;

    // Push-to-talk: hold to record
    btn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      this.startRecording();
    });

    btn.addEventListener('mouseup', (e) => {
      e.preventDefault();
      this.stopRecording();
    });

    btn.addEventListener('mouseleave', () => {
      if (this.isRecording) {
        this.stopRecording();
      }
    });

    // Touch support
    btn.addEventListener('touchstart', (e) => {
      e.preventDefault();
      this.startRecording();
    });

    btn.addEventListener('touchend', (e) => {
      e.preventDefault();
      this.stopRecording();
    });

    // Keyboard: Space to toggle (when chat input is not focused)
    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        this.toggleRecording();
      }
    });

    // Listen for voice state changes from backend
    this.ipc.on('voice_state', (_evt: string, data: any) => {
      this.updateState(data.state);
    });

    // Listen for transcripts
    this.ipc.on('voice_state', (_evt: string, data: any) => {
      if (data.transcript) {
        this.showTranscript(data.transcript);
      }
    });
  }

  private async startRecording(): Promise<void> {
    if (this.isRecording) return;

    this.isRecording = true;
    this.updateState('listening');

    try {
      const result = await this.ipc.voiceListen(5);
      if (result?.transcript) {
        this.showTranscript(result.transcript);
        // Auto-send the transcript as a chat message
        this.ipc.chatStream(result.transcript);
        this.updateState('thinking');
      }
    } catch (e) {
      console.error('Voice recording error:', e);
      this.updateState('error');
    } finally {
      this.isRecording = false;
      // State will be updated by backend voice_state events
    }
  }

  private stopRecording(): void {
    if (!this.isRecording) return;
    this.isRecording = false;
    if (this.recordTimer) {
      clearTimeout(this.recordTimer);
      this.recordTimer = null;
    }
  }

  private toggleRecording(): void {
    if (this.isRecording) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  }

  private updateState(state: VoiceState): void {
    this.state = state;
    const btn = this.element.querySelector('.voice-btn') as HTMLElement;
    const indicator = this.element.querySelector('.voice-indicator') as HTMLElement;
    const stateText = this.element.querySelector('.voice-state-text') as HTMLElement;

    // Remove all state classes
    btn.className = `voice-btn ${state}`;
    indicator.className = `voice-indicator ${state}`;

    const labels: Record<VoiceState, string> = {
      idle: 'Voice Ready',
      listening: 'Listening...',
      thinking: 'Thinking...',
      speaking: 'Speaking...',
      working: 'Working...',
      error: 'Error',
    };
    stateText.textContent = labels[state] || state;
  }

  private showTranscript(text: string): void {
    const transcript = this.element.querySelector('.voice-transcript') as HTMLElement;
    if (transcript) {
      transcript.textContent = text;
      transcript.style.display = 'block';
      // Fade out after 5 seconds
      setTimeout(() => {
        transcript.style.display = 'none';
      }, 5000);
    }
  }

  public getState(): VoiceState {
    return this.state;
  }
}
