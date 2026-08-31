// WebSearch Component — web search, documentation lookup, page fetch

import { IPCClient } from '../lib/ipc';

interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  display_url?: string;
  source?: string;
}

type SearchMode = 'search' | 'docs';

export class WebSearch {
  private element: HTMLElement;
  private ipc: IPCClient;
  private results: SearchResult[] = [];
  private currentMode: SearchMode = 'search';
  private isOpen = false;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'web-search';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="ws-header">
        <span class="ws-title">🌐 Web Search</span>
        <button class="ws-close" title="Close">✕</button>
      </div>
      <div class="ws-tabs">
        <button class="ws-tab active" data-mode="search">🔍 Search</button>
        <button class="ws-tab" data-mode="docs">📚 Docs</button>
      </div>
      <div class="ws-search-bar">
        <input type="text" class="ws-input" placeholder="Search the web..." />
        <button class="ws-search-btn">Search</button>
      </div>
      <div class="ws-results"></div>
      <div class="ws-content-panel" style="display:none">
        <div class="ws-content-header">
          <span class="ws-content-title"></span>
          <button class="ws-content-close">✕</button>
        </div>
        <div class="ws-content-body"></div>
      </div>
    `;
    return div;
  }

  private mount(): void {
    const main = document.querySelector('.main');
    if (main) {
      main.appendChild(this.element);
    }
  }

  private setupListeners(): void {
    const input = this.element.querySelector('.ws-input') as HTMLInputElement;
    const searchBtn = this.element.querySelector('.ws-search-btn');

    searchBtn?.addEventListener('click', () => this.doSearch());
    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.doSearch();
    });

    this.element.querySelector('.ws-close')?.addEventListener('click', () => this.hide());

    // Tab switching
    this.element.querySelectorAll('.ws-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this.element.querySelectorAll('.ws-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.currentMode = (tab as HTMLElement).dataset.mode as SearchMode;
        const input = this.element.querySelector('.ws-input') as HTMLInputElement;
        if (this.currentMode === 'docs') {
          input.placeholder = 'Search documentation (e.g., "python asyncio")...';
        } else {
          input.placeholder = 'Search the web...';
        }
      });
    });

    // Content panel close
    this.element.querySelector('.ws-content-close')?.addEventListener('click', () => {
      const panel = this.element.querySelector('.ws-content-panel') as HTMLElement;
      if (panel) panel.style.display = 'none';
    });
  }

  private async doSearch(): Promise<void> {
    const input = this.element.querySelector('.ws-input') as HTMLInputElement;
    const query = input?.value?.trim();
    if (!query) return;

    const resultsEl = this.element.querySelector('.ws-results') as HTMLElement;
    if (resultsEl) resultsEl.innerHTML = '<div class="ws-loading">Searching...</div>';

    try {
      if (this.currentMode === 'docs') {
        const result = await this.ipc.request('internet.docs', { query });
        this.results = (result.results || []).map((r: any) => ({
          title: r.title,
          url: r.url,
          snippet: r.summary || '',
          source: r.source || '',
        }));
      } else {
        const result = await this.ipc.request('internet.search', { query, max_results: 10 });
        this.results = result.results || [];
      }

      this.renderResults();
    } catch (e) {
      if (resultsEl) resultsEl.innerHTML = `<div class="ws-error">Search failed: ${(e as Error).message}</div>`;
    }
  }

  private renderResults(): void {
    const resultsEl = this.element.querySelector('.ws-results') as HTMLElement;
    if (!resultsEl) return;

    if (this.results.length === 0) {
      resultsEl.innerHTML = '<div class="ws-empty">No results found</div>';
      return;
    }

    resultsEl.innerHTML = this.results.map((r, i) => `
      <div class="ws-result" data-index="${i}">
        <div class="ws-result-url">${r.display_url || r.url || ''}</div>
        <div class="ws-result-title">${this.escapeHtml(r.title)}</div>
        <div class="ws-result-snippet">${this.escapeHtml(r.snippet)}</div>
        ${r.source ? `<div class="ws-result-source">${r.source}</div>` : ''}
      </div>
    `).join('');

    resultsEl.querySelectorAll('.ws-result').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt((el as HTMLElement).dataset.index || '0');
        const result = this.results[idx];
        if (result?.url) {
          this.openContent(result.url, result.title);
        }
      });
    });
  }

  private async openContent(url: string, title: string): Promise<void> {
    const panel = this.element.querySelector('.ws-content-panel') as HTMLElement;
    const contentTitle = this.element.querySelector('.ws-content-title') as HTMLElement;
    const contentBody = this.element.querySelector('.ws-content-body') as HTMLElement;

    if (panel) panel.style.display = 'flex';
    if (contentTitle) contentTitle.textContent = title || url;
    if (contentBody) contentBody.innerHTML = '<div class="ws-loading">Loading page...</div>';

    try {
      const result = await this.ipc.request('internet.fetch', { url, max_chars: 15000 });
      if (contentBody) {
        contentBody.innerHTML = `<div class="ws-fetched-content"><pre>${this.escapeHtml(result.content || 'Empty page')}</pre></div>`;
      }
    } catch (e) {
      if (contentBody) contentBody.innerHTML = `<div class="ws-error">Failed to load: ${(e as Error).message}</div>`;
    }
  }

  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  show(): void {
    this.element.style.display = 'flex';
    this.isOpen = true;
    const input = this.element.querySelector('.ws-input') as HTMLInputElement;
    input?.focus();
  }

  hide(): void {
    this.element.style.display = 'none';
    this.isOpen = false;
  }

  toggle(): void {
    if (this.isOpen) {
      this.hide();
    } else {
      this.show();
    }
  }
}
