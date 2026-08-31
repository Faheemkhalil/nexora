// Plugin Manager — view, install, enable/disable, and manage NEXORA plugins

import { IPCClient } from '../lib/ipc';

export class PluginManager {
  private element: HTMLElement;
  private ipc: IPCClient;
  private installed: any[] = [];
  private available: any[] = [];

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.loadData();
  }

  private createElement(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'plugin-manager hidden';
    el.innerHTML = `
      <div class="plugin-manager-header">
        <h2>Plugin Manager</h2>
        <p class="plugin-subtitle">Manage installed plugins and browse available extensions</p>
      </div>
      <div class="plugin-tabs">
        <button class="plugin-tab active" data-tab="installed">Installed</button>
        <button class="plugin-tab" data-tab="available">Available</button>
      </div>
      <div class="plugin-content" id="plugin-content"></div>
    `;
    return el;
  }

  private mount(): void {
    const app = document.getElementById('app');
    if (app) app.appendChild(this.element);

    this.element.querySelectorAll('.plugin-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        this.element.querySelectorAll('.plugin-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.renderTab((btn as HTMLElement).dataset.tab || 'installed');
      });
    });
  }

  async loadData(): Promise<void> {
    try {
      const [installedRes, availableRes] = await Promise.all([
        this.ipc.request('plugins.installed', {}),
        this.ipc.request('plugins.list', {}),
      ]);
      this.installed = (installedRes as any)?.plugins || [];
      this.available = (availableRes as any)?.plugins || [];
      this.renderTab('installed');
    } catch (e) {
      console.error('Failed to load plugins:', e);
    }
  }

  private renderTab(tab: string): void {
    const content = this.element.querySelector('#plugin-content');
    if (!content) return;

    if (tab === 'installed') {
      this.renderInstalled(content);
    } else {
      this.renderAvailable(content);
    }
  }

  private renderInstalled(container: Element): void {
    if (this.installed.length === 0) {
      container.innerHTML = `
        <div class="plugin-empty">
          <div class="plugin-empty-icon">📦</div>
          <h3>No plugins installed</h3>
          <p>Browse the Available tab to install plugins</p>
        </div>
      `;
      return;
    }

    container.innerHTML = this.installed.map(p => `
      <div class="plugin-card" data-id="${p.id}">
        <div class="plugin-card-header">
          <div class="plugin-card-info">
            <h3 class="plugin-card-name">${p.name}</h3>
            <span class="plugin-card-version">v${p.version}</span>
            <span class="plugin-card-author">by ${p.author}</span>
          </div>
          <div class="plugin-card-actions">
            <label class="plugin-toggle">
              <input type="checkbox" ${p.enabled ? 'checked' : ''} data-id="${p.id}" />
              <span class="plugin-toggle-slider"></span>
            </label>
            <button class="plugin-btn plugin-btn-danger" data-uninstall="${p.id}" title="Uninstall">✕</button>
          </div>
        </div>
        <p class="plugin-card-desc">${p.description}</p>
        <div class="plugin-card-meta">
          <span>Installed ${new Date(p.installed_at * 1000).toLocaleDateString()}</span>
        </div>
      </div>
    `).join('');

    // Toggle handlers
    container.querySelectorAll('.plugin-toggle input').forEach(input => {
      input.addEventListener('change', async (e) => {
        const id = (e.target as HTMLElement).getAttribute('data-id');
        const enabled = (e.target as HTMLInputElement).checked;
        if (id) {
          await this.ipc.request('plugins.toggle', { id, enabled });
        }
      });
    });

    // Uninstall handlers
    container.querySelectorAll('[data-uninstall]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = (e.target as HTMLElement).getAttribute('data-uninstall');
        if (id && confirm('Uninstall this plugin?')) {
          await this.ipc.request('plugins.uninstall', { id });
          await this.loadData();
        }
      });
    });
  }

  private renderAvailable(container: Element): void {
    container.innerHTML = this.available.map(p => `
      <div class="plugin-card" data-name="${p.name}">
        <div class="plugin-card-header">
          <div class="plugin-card-info">
            <h3 class="plugin-card-name">${p.icon || '📦'} ${p.name}</h3>
            <span class="plugin-card-version">v${p.version}</span>
            <span class="plugin-card-author">by ${p.author}</span>
          </div>
          <button class="plugin-btn plugin-btn-install" data-install="${p.name}">Install</button>
        </div>
        <p class="plugin-card-desc">${p.description}</p>
        <div class="plugin-card-tags">
          ${(p.tags || []).map((t: string) => `<span class="plugin-tag">${t}</span>`).join('')}
        </div>
      </div>
    `).join('');

    container.querySelectorAll('[data-install]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const name = (e.target as HTMLElement).getAttribute('data-install');
        if (name) {
          const plugin = this.available.find(p => p.name === name);
          await this.ipc.request('plugins.install', {
            name,
            version: plugin?.version || 'latest',
            manifest: plugin,
          });
          await this.loadData();
        }
      });
    });
  }

  show(): void { this.element.classList.remove('hidden'); }
  hide(): void { this.element.classList.add('hidden'); }
  isVisible(): boolean { return !this.element.classList.contains('hidden'); }
}
