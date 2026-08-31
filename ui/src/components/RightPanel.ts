// Right Panel — System Status, Provider, Active Task

import { IPCClient } from '../lib/ipc';

export class RightPanel {
  private element: HTMLElement;
  private ipc: IPCClient;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('aside');
    div.className = 'rightpanel';
    div.innerHTML = `
      <div class="panel-card">
        <div class="panel-title">Provider</div>
        <div class="provider-indicator">
          <div class="provider-dot" id="provider-dot"></div>
          <div>
            <div id="provider-name">No provider</div>
            <div id="provider-model" style="font-size: 11px; color: var(--fg-muted);"></div>
          </div>
        </div>
      </div>
      <div class="panel-card">
        <div class="panel-title">System Status</div>
        <div class="status-grid" id="status-grid"></div>
      </div>
      <div class="panel-card">
        <div class="panel-title">Active Task</div>
        <div id="active-task">No active task</div>
      </div>
      <div class="panel-card">
        <div class="panel-title">Recent Findings</div>
        <div id="recent-findings">No findings</div>
      </div>
      <div class="panel-card">
        <div class="panel-title">Tool Activity</div>
        <div id="tool-activity">Idle</div>
      </div>
    `;
    return div;
  }

  private mount(): void {
    const app = document.getElementById('app');
    if (app) {
      app.appendChild(this.element);
    }
  }

  private setupListeners(): void {
    this.ipc.on('connected', () => this.refresh());
    this.ipc.on('providers.list', () => this.refresh());
  }

  async refresh(): Promise<void> {
    try {
      const providers = await this.ipc.listProviders();
      this.updateProviderInfo(providers);
      this.updateSystemStatus();
    } catch (e) {
      console.warn('RightPanel refresh failed:', e);
    }
  }

  private updateProviderInfo(providers: any[]): void {
    const dot = this.element.querySelector('#provider-dot') as HTMLElement;
    const nameEl = this.element.querySelector('#provider-name') as HTMLElement;
    const modelEl = this.element.querySelector('#provider-model') as HTMLElement;

    const configured = providers.find(p => p.configured);
    if (configured) {
      dot.className = 'provider-dot connected';
      nameEl.textContent = configured.name;
      modelEl.textContent = configured.model;
    } else if (providers.length > 0) {
      dot.className = 'provider-dot';
      nameEl.textContent = providers[0].name + ' (not configured)';
      modelEl.textContent = providers[0].model;
    } else {
      dot.className = 'provider-dot error';
      nameEl.textContent = 'No provider configured';
      modelEl.textContent = 'Add a provider in Settings';
    }
  }

  private updateSystemStatus(): void {
    const grid = this.element.querySelector('#status-grid') as HTMLElement;
    grid.innerHTML = `
      <div class="status-item">
        <span class="status-label">Mode</span>
        <span class="status-value online">Online</span>
      </div>
      <div class="status-item">
        <span class="status-label">Voice</span>
        <span class="status-value offline">Idle</span>
      </div>
      <div class="status-item">
        <span class="status-label">Uptime</span>
        <span class="status-value">${this.formatUptime()}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Memory</span>
        <span class="status-value">${this.getMemoryUsage()}</span>
      </div>
    `;
  }

  private formatUptime(): string {
    const seconds = Math.floor((Date.now() - (window as any).__NEXORA_START_TIME__ || Date.now()) / 1000);
    const mins = Math.floor(seconds / 60);
    const hrs = Math.floor(mins / 60);
    if (hrs > 0) return `${hrs}h ${mins % 60}m`;
    return `${mins}m`;
  }

  private getMemoryUsage(): string {
    if ((window as any).performance?.memory) {
      const mem = (window as any).performance.memory;
      return `${Math.round(mem.usedJSHeapSize / 1024 / 1024)} MB`;
    }
    return 'N/A';
  }
}