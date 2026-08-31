// FileExplorer Component — directory listing, file navigation, file preview

import { IPCClient } from '../lib/ipc';

interface FileEntry {
  name: string;
  type: 'file' | 'dir';
  size: number | null;
  modified: number;
  path: string;
}

export class FileExplorer {
  private element: HTMLElement;
  private ipc: IPCClient;
  private currentPath: string = '/';
  private entries: FileEntry[] = [];

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'file-explorer';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="file-header">
        <button class="file-nav-btn" id="file-up" title="Go up">↑</button>
        <input type="text" class="file-path-input" value="/" placeholder="Path..." />
        <button class="file-nav-btn" id="file-refresh" title="Refresh">↻</button>
      </div>
      <div class="file-list"></div>
    `;
    return div;
  }

  private mount(): void {
    const rightPanel = document.querySelector('.rightpanel');
    if (rightPanel) {
      rightPanel.insertBefore(this.element, rightPanel.firstChild);
    }
  }

  private setupListeners(): void {
    const pathInput = this.element.querySelector('.file-path-input') as HTMLInputElement;
    const upBtn = this.element.querySelector('#file-up');
    const refreshBtn = this.element.querySelector('#file-refresh');

    pathInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.navigateTo(pathInput.value);
      }
    });

    upBtn?.addEventListener('click', () => {
      const parts = this.currentPath.split('/').filter(Boolean);
      parts.pop();
      this.navigateTo('/' + parts.join('/') || '/');
    });

    refreshBtn?.addEventListener('click', () => this.refresh());
  }

  async navigateTo(path: string): Promise<void> {
    this.currentPath = path;
    const pathInput = this.element.querySelector('.file-path-input') as HTMLInputElement;
    pathInput.value = path;

    try {
      const result = await this.ipc.request('tools.execute', {
        name: 'file.list',
        inputs: { path, show_hidden: false },
        confirmed: true,
      });

      if (result.entries) {
        this.entries = result.entries;
        this.renderEntries();
      }
    } catch (e) {
      console.warn('File list failed:', e);
    }
  }

  private renderEntries(): void {
    const list = this.element.querySelector('.file-list') as HTMLElement;
    if (!list) return;

    // Directories first, then files
    const sorted = [...this.entries].sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

    list.innerHTML = sorted.map(entry => `
      <div class="file-entry ${entry.type}" data-path="${entry.path}" data-type="${entry.type}">
        <span class="file-icon">${entry.type === 'dir' ? '📁' : '📄'}</span>
        <span class="file-name">${entry.name}</span>
        <span class="file-size">${entry.type === 'file' ? this.formatSize(entry.size || 0) : '—'}</span>
      </div>
    `).join('');

    list.querySelectorAll('.file-entry').forEach(el => {
      el.addEventListener('click', () => {
        const type = (el as HTMLElement).dataset.type;
        const path = (el as HTMLElement).dataset.path;
        if (type === 'dir' && path) {
          this.navigateTo(path);
        }
      });
    });
  }

  private formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async refresh(): Promise<void> {
    await this.navigateTo(this.currentPath);
  }

  show(): void {
    this.element.style.display = 'block';
    if (this.entries.length === 0) {
      this.navigateTo(this.currentPath);
    }
  }

  hide(): void {
    this.element.style.display = 'none';
  }
}
