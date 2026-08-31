// Settings Modal

import { IPCClient } from '../lib/ipc';

const aiIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="19" x2="8" y2="22"/><line x1="16" y1="19" x2="16" y2="22"/></svg>`;
const serverIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01"/><path d="M8 14h.01M12 14h.01M16 14h.01"/><path d="M6 18h.01M10 18h.01M14 18h.01M18 18h.01"/></svg>`;
const voiceIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="19" x2="8" y2="22"/><line x1="16" y1="19" x2="16" y2="22"/></svg>`;
const monitorIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
const globeIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;
const codeIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
const shieldIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`;
const databaseIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/></svg>`;
const paletteIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="18" cy="12" r="2"/><circle cx="11" cy="18" r="3"/></svg>`;
const lockIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;

const SETTINGS_TABS = [
  { id: 'ai', label: 'AI', icon: aiIcon },
  { id: 'providers', label: 'Providers', icon: serverIcon },
  { id: 'voice', label: 'Voice', icon: voiceIcon },
  { id: 'pc', label: 'PC Control', icon: monitorIcon },
  { id: 'internet', label: 'Internet', icon: globeIcon },
  { id: 'coding', label: 'Coding', icon: codeIcon },
  { id: 'security', label: 'Security', icon: shieldIcon },
  { id: 'memory', label: 'Memory', icon: databaseIcon },
  { id: 'appearance', label: 'Appearance', icon: paletteIcon },
  { id: 'privacy', label: 'Privacy', icon: lockIcon },
];

export class SettingsModal {
  private element: HTMLElement | null = null;
  private ipc: IPCClient;
  private activeTab = 'ai';
  private _escHandler: ((e: KeyboardEvent) => void) | null = null;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
  }

  open(): void {
    if (!this.element) {
      this.createElement();
    }
    this.element!.classList.add('open');
    document.body.style.overflow = 'hidden';
    this.loadProviders();

    // Escape key handler
    if (!this._escHandler) {
      this._escHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && this.element?.classList.contains('open')) {
          this.close();
        }
      };
      document.addEventListener('keydown', this._escHandler);
    }
  }

  close(): void {
    this.element?.classList.remove('open');
    document.body.style.overflow = '';
    if (this._escHandler) {
      document.removeEventListener('keydown', this._escHandler);
      this._escHandler = null;
    }
  }

  private createElement(): void {
    this.element = document.createElement('div');
    this.element.className = 'modal-overlay';
    this.element.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">NEXORA Settings</h2>
          <button class="modal-close" aria-label="Close">&times;</button>
        </div>
        <div class="modal-content">
          <div class="modal-tabs" id="settings-tabs"></div>
          <div class="modal-panels" id="settings-panels"></div>
        </div>
      </div>
    `;

    document.body.appendChild(this.element);

    // Tab click handlers
    this.element.querySelector('.modal-close')?.addEventListener('click', () => this.close());
    this.element.addEventListener('click', (e) => {
      if (e.target === this.element) this.close();
    });

    this.renderTabs();
    this.renderPanels();
  }

  private renderTabs(): void {
    const container = this.element!.querySelector('#settings-tabs') as HTMLElement;
    container.innerHTML = SETTINGS_TABS.map(tab => `
      <button class="modal-tab ${tab.id === this.activeTab ? 'active' : ''}" data-tab="${tab.id}">
        ${tab.icon}<span>${tab.label}</span>
      </button>
    `).join('');

    container.querySelectorAll('.modal-tab').forEach((btn: Element) => {
      (btn as HTMLElement).addEventListener('click', () => this.switchTab((btn as HTMLElement).dataset.tab!));
    });
  }

  private renderPanels(): void {
    const container = this.element!.querySelector('#settings-panels') as HTMLElement;
    container.innerHTML = SETTINGS_TABS.map(tab => `
      <div class="modal-panel ${tab.id === this.activeTab ? 'active' : ''}" id="panel-${tab.id}"></div>
    `).join('');

    this.renderPanelContent(this.activeTab);
  }

  private switchTab(tabId: string): void {
    this.activeTab = tabId;
    this.element!.querySelectorAll('.modal-tab').forEach((btn: Element) => {
      const btnEl = btn as HTMLElement;
      btnEl.classList.toggle('active', btnEl.dataset.tab === tabId);
    });
    this.element!.querySelectorAll('.modal-panel').forEach(panel => {
      panel.classList.toggle('active', panel.id === `panel-${tabId}`);
    });
    this.renderPanelContent(tabId);
  }

  private renderPanelContent(tabId: string): void {
    const panel = this.element!.querySelector(`#panel-${tabId}`) as HTMLElement;
    if (!panel) return;

    switch (tabId) {
      case 'ai':
        panel.innerHTML = this.renderAISettings();
        break;
      case 'providers':
        panel.innerHTML = this.renderProvidersSettings();
        break;
      case 'voice':
        panel.innerHTML = this.renderVoiceSettings();
        break;
      case 'appearance':
        panel.innerHTML = this.renderAppearanceSettings();
        break;
      case 'privacy':
        panel.innerHTML = this.renderPrivacySettings();
        break;
      default:
        panel.innerHTML = `<div style="color: var(--fg-muted); padding: 20px;">${tabId} settings coming soon...</div>`;
    }
    this.bindPanelEvents(tabId);
  }

  private renderAISettings(): string {
    return `
      <div class="setting-row">
        <span class="setting-label">Default Temperature</span>
        <div class="setting-control">
          <input type="range" class="setting-input" id="ai-temp" min="0" max="2" step="0.1" value="0.7" style="width: 200px;" />
          <span id="ai-temp-value">0.7</span>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Default Context (tokens)</span>
        <div class="setting-control">
          <select class="setting-select" id="ai-context">
            <option value="2048">2048</option>
            <option value="4096" selected>4096</option>
            <option value="8192">8192</option>
            <option value="16384">16384</option>
            <option value="32768">32768</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Streaming Responses</span>
        <div class="setting-control">
          <div class="toggle active" id="ai-streaming" role="switch" aria-checked="true"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Offline Fallback</span>
        <div class="setting-control">
          <div class="toggle active" id="ai-offline" role="switch" aria-checked="true"></div>
        </div>
      </div>
    `;
  }

  private renderProvidersSettings(): string {
    return `
      <div style="margin-bottom: 16px;">
        <button class="chat-send" id="add-provider-btn" style="width: 100%;">Add Provider</button>
      </div>
      <div id="providers-list"></div>
      <div id="provider-form" style="display: none;"></div>
    `;
  }

  private renderVoiceSettings(): string {
    return `
      <div class="setting-row">
        <span class="setting-label">Microphone</span>
        <div class="setting-control">
          <select class="setting-select" id="voice-mic"><option value="default">System Default</option></select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Speech-to-Text Engine</span>
        <div class="setting-control">
          <select class="setting-select" id="voice-stt">
            <option value="google">Google (online, free)</option>
            <option value="whisper">Whisper (local, requires GPU)</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Text-to-Speech Engine</span>
        <div class="setting-control">
          <select class="setting-select" id="voice-tts">
            <option value="edge">Edge TTS (online, high quality)</option>
            <option value="espeak">espeak-ng (offline, basic)</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Language</span>
        <div class="setting-control">
          <select class="setting-select" id="voice-lang">
            <option value="en-US" selected>English (US)</option>
            <option value="en-GB">English (UK)</option>
            <option value="es-ES">Spanish</option>
            <option value="fr-FR">French</option>
            <option value="de-DE">German</option>
            <option value="ja-JP">Japanese</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Push to Talk</span>
        <div class="setting-control">
          <div class="toggle active" id="voice-ptt" role="switch" aria-checked="true"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Wake Word</span>
        <div class="setting-control">
          <input type="text" class="setting-input" id="voice-wake" placeholder="e.g. Hey NEXORA" />
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Volume</span>
        <div class="setting-control">
          <input type="range" class="setting-input" id="voice-volume" min="0" max="1" step="0.1" value="0.8" style="width: 200px;" />
        </div>
      </div>
    `;
  }

  private renderAppearanceSettings(): string {
    return `
      <div class="setting-row">
        <span class="setting-label">Theme</span>
        <div class="setting-control">
          <select class="setting-select" id="ui-theme">
            <option value="dark" selected>Dark</option>
            <option value="light">Light</option>
            <option value="auto">Auto</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Reduced Motion</span>
        <div class="setting-control">
          <div class="toggle" id="ui-reduced-motion" role="switch" aria-checked="false"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">3D Effects</span>
        <div class="setting-control">
          <div class="toggle active" id="ui-3d-effects" role="switch" aria-checked="true"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">HUD Density</span>
        <div class="setting-control">
          <select class="setting-select" id="ui-hud">
            <option value="minimal">Minimal</option>
            <option value="normal" selected>Normal</option>
            <option value="dense">Dense</option>
          </select>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Fullscreen</span>
        <div class="setting-control">
          <div class="toggle" id="ui-fullscreen" role="switch" aria-checked="false"></div>
        </div>
      </div>
    `;
  }

  private renderPrivacySettings(): string {
    return `
      <div class="setting-row">
        <span class="setting-label">Local-Only Mode</span>
        <div class="setting-control">
          <div class="toggle" id="privacy-local" role="switch" aria-checked="false"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Store Conversations</span>
        <div class="setting-control">
          <div class="toggle active" id="privacy-conv" role="switch" aria-checked="true"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Application Logs</span>
        <div class="setting-control">
          <div class="toggle active" id="privacy-logs" role="switch" aria-checked="true"></div>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Credentials in Keychain</span>
        <div class="setting-control">
          <div class="toggle active" id="privacy-creds" role="switch" aria-checked="true"></div>
        </div>
      </div>
    `;
  }

  private bindPanelEvents(tabId: string): void {
    const panel = this.element!.querySelector(`#panel-${tabId}`);
    if (!panel) return;

    // Temperature slider
    const tempSlider = panel.querySelector('#ai-temp') as HTMLInputElement;
    const tempValue = panel.querySelector('#ai-temp-value');
    if (tempSlider) {
      tempSlider.addEventListener('input', () => {
        if (tempValue) tempValue.textContent = tempSlider.value;
        this.ipc.setSetting('ai.temperature', parseFloat(tempSlider.value));
      });
    }

    // Context select
    const contextSelect = panel.querySelector('#ai-context') as HTMLSelectElement;
    if (contextSelect) {
      contextSelect.addEventListener('change', () => {
        this.ipc.setSetting('ai.context', parseInt(contextSelect.value));
      });
    }

    // Toggles
    panel.querySelectorAll('.toggle').forEach(toggle => {
      toggle.addEventListener('click', () => {
        toggle.classList.toggle('active');
        const key = toggle.id.replace(/^(ai|ui|voice|privacy)-/, '');
        const prefix = tabId === 'voice' ? 'voice' : tabId === 'appearance' ? 'ui' : tabId === 'privacy' ? 'privacy' : 'ai';
        this.ipc.setSetting(`${prefix}.${key}`, toggle.classList.contains('active'));
      });
    });

    // Add provider button
    const addBtn = panel.querySelector('#add-provider-btn');
    if (addBtn) {
      addBtn.addEventListener('click', () => this.showAddProviderForm());
    }

    // Voice settings
    if (tabId === 'voice') {
      const sttSelect = panel.querySelector('#voice-stt') as HTMLSelectElement;
      const ttsSelect = panel.querySelector('#voice-tts') as HTMLSelectElement;
      const langSelect = panel.querySelector('#voice-lang') as HTMLSelectElement;
      const wakeInput = panel.querySelector('#voice-wake') as HTMLInputElement;

      sttSelect?.addEventListener('change', () => {
        this.ipc.configureVoice({ stt_engine: sttSelect.value });
      });
      ttsSelect?.addEventListener('change', () => {
        this.ipc.configureVoice({ tts_engine: ttsSelect.value });
      });
      langSelect?.addEventListener('change', () => {
        this.ipc.configureVoice({ language: langSelect.value });
      });
      wakeInput?.addEventListener('change', () => {
        this.ipc.setSetting('voice.wake_word', wakeInput.value || null);
      });
    }
  }

  private async loadProviders(): Promise<void> {
    try {
      await this.ipc.listProviders();
      if (this.activeTab === 'providers') {
        this.renderPanelContent('providers');
      }
    } catch (e) {
      console.warn('Failed to load providers:', e);
    }
  }

  private showAddProviderForm(): void {
    const listEl = this.element!.querySelector('#providers-list') as HTMLElement;
    const formEl = this.element!.querySelector('#provider-form') as HTMLElement;

    formEl.style.display = 'block';
    formEl.innerHTML = `
      <div style="background: var(--bg-tertiary); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
        <h4 style="margin-bottom: 12px;">Add New Provider</h4>
        <div class="setting-row">
          <span class="setting-label">Type</span>
          <div class="setting-control">
            <select class="setting-select" id="new-provider-type">
              <option value="openrouter">OpenRouter</option>
              <option value="custom">Custom (OpenAI-compatible)</option>
              <option value="local">Local (Ollama/llama.cpp)</option>
            </select>
          </div>
        </div>
        <div class="setting-row">
          <span class="setting-label">Name</span>
          <div class="setting-control">
            <input type="text" class="setting-input" id="new-provider-name" placeholder="My Provider" />
          </div>
        </div>
        <div class="setting-row">
          <span class="setting-label">Model</span>
          <div class="setting-control">
            <input type="text" class="setting-input" id="new-provider-model" placeholder="gpt-3.5-turbo" />
          </div>
        </div>
        <div class="setting-row" id="new-provider-key-row">
          <span class="setting-label">API Key</span>
          <div class="setting-control">
            <input type="password" class="setting-input" id="new-provider-key" placeholder="sk-..." />
          </div>
        </div>
        <div class="setting-row" id="new-provider-url-row" style="display: none;">
          <span class="setting-label">Base URL</span>
          <div class="setting-control">
            <input type="text" class="setting-input" id="new-provider-url" placeholder="https://api.example.com/v1" />
          </div>
        </div>
        <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px;">
          <button class="chat-send" id="save-provider">Save</button>
          <button class="chat-send" id="cancel-provider" style="background: var(--bg-tertiary); color: var(--fg-secondary);">Cancel</button>
        </div>
      </div>
    `;

    listEl.style.display = 'none';

    // Type change handler
    const typeSelect = formEl.querySelector('#new-provider-type') as HTMLSelectElement;
    typeSelect.addEventListener('change', () => {
      const keyRow = formEl.querySelector('#new-provider-key-row') as HTMLElement;
      const urlRow = formEl.querySelector('#new-provider-url-row') as HTMLElement;
      if (typeSelect.value === 'local') {
        keyRow.style.display = 'none';
        urlRow.style.display = 'grid';
      } else {
        keyRow.style.display = 'grid';
        urlRow.style.display = typeSelect.value === 'custom' ? 'grid' : 'none';
      }
    });

    formEl.querySelector('#save-provider')?.addEventListener('click', async () => {
      const type = (formEl.querySelector('#new-provider-type') as HTMLSelectElement).value;
      const name = (formEl.querySelector('#new-provider-name') as HTMLInputElement).value;
      const model = (formEl.querySelector('#new-provider-model') as HTMLInputElement).value;
      const apiKey = (formEl.querySelector('#new-provider-key') as HTMLInputElement).value;
      const baseUrl = (formEl.querySelector('#new-provider-url') as HTMLInputElement).value;

      if (!name || !model) {
        alert('Name and model are required');
        return;
      }

      try {
        await this.ipc.addProvider(type, name, model, apiKey || undefined, baseUrl || undefined);
        formEl.style.display = 'none';
        listEl.style.display = 'block';
        this.loadProviders();
      } catch (e) {
        alert(`Failed to add provider: ${(e as Error).message}`);
      }
    });

    formEl.querySelector('#cancel-provider')?.addEventListener('click', () => {
      formEl.style.display = 'none';
      listEl.style.display = 'block';
    });
  }
}