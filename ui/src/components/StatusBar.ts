// Status Bar — Bottom bar with connection, mode, provider, voice status

import { IPCClient } from '../lib/ipc';

export class StatusBar {
  private element: HTMLElement;
  private ipc: IPCClient;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('footer');
    div.className = 'statusbar';
    div.innerHTML = `
      <div class="statusbar-left">
        <div class="statusbar-item">
          <span class="statusbar-dot gray" id="conn-dot"></span>
          <span id="conn-text">Disconnected</span>
        </div>
        <div class="statusbar-item">
          <span class="statusbar-dot green" id="mode-dot"></span>
          <span id="mode-text">Online</span>
        </div>
      </div>
      <div class="statusbar-right">
        <div class="statusbar-item">
          <span id="provider-text">No provider</span>
        </div>
        <div class="statusbar-item">
          <span class="statusbar-dot gray" id="voice-dot"></span>
          <span id="voice-text">Voice: Off</span>
        </div>
        <div class="statusbar-item">
          <span id="time-text"></span>
        </div>
      </div>
    `;
    return div;
  }

  private mount(): void {
    const app = document.getElementById('app');
    if (app) {
      app.appendChild(this.element);
    }
    this.updateTime();
    setInterval(() => this.updateTime(), 1000);
  }

  private setupListeners(): void {
    this.ipc.on('connected', () => this.updateConnection(true));
    this.ipc.on('disconnected', () => this.updateConnection(false));
    this.ipc.on('voice_state', (_evt: string, data: any) => this.updateVoice(data));
  }

  async refresh(): Promise<void> {
    try {
      const providers = await this.ipc.listProviders();
      const configured = providers.find((p: any) => p.configured);
      const textEl = this.element.querySelector('#provider-text') as HTMLElement;
      if (configured) {
        textEl.textContent = `${configured.name} • ${configured.model}`;
      } else if (providers.length > 0) {
        textEl.textContent = `${providers[0].name} • ${providers[0].model} (not configured)`;
      } else {
        textEl.textContent = 'No provider configured';
      }
    } catch (e) {
      console.warn('StatusBar refresh failed:', e);
    }
  }

  private updateConnection(connected: boolean): void {
    const dot = this.element.querySelector('#conn-dot') as HTMLElement;
    const text = this.element.querySelector('#conn-text') as HTMLElement;
    if (connected) {
      dot.className = 'statusbar-dot green';
      text.textContent = 'Connected';
    } else {
      dot.className = 'statusbar-dot red';
      text.textContent = 'Disconnected';
    }
  }

  private updateVoice(data: any): void {
    const dot = this.element.querySelector('#voice-dot') as HTMLElement;
    const text = this.element.querySelector('#voice-text') as HTMLElement;
    const state = data.state || 'idle';
    const colors: Record<string, string> = {
      idle: 'gray',
      listening: 'green',
      thinking: 'yellow',
      speaking: 'green',
      working: 'yellow',
      error: 'red',
    };
    dot.className = `statusbar-dot ${colors[state] || 'gray'}`;
    text.textContent = `Voice: ${state.charAt(0).toUpperCase() + state.slice(1)}`;
  }

  private updateTime(): void {
    const text = this.element.querySelector('#time-text') as HTMLElement;
    if (text) {
      text.textContent = new Date().toLocaleTimeString();
    }
  }
}