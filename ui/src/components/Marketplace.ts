// Marketplace — browse, search, and install NEXORA extensions

import { IPCClient } from '../lib/ipc';

export class Marketplace {
  private element: HTMLElement;
  private ipc: IPCClient;
  private featured: any[] = [];
  private trending: any[] = [];
  private categories: any[] = [];
  private searchResults: any[] = [];
  private stats: any = {};

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.loadData();
  }

  private createElement(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'marketplace hidden';
    el.innerHTML = `
      <div class="marketplace-header">
        <h2>Extension Marketplace</h2>
        <p class="marketplace-subtitle">Discover and install NEXORA extensions</p>
        <div class="marketplace-stats" id="mp-stats"></div>
      </div>
      <div class="marketplace-search">
        <input type="text" id="mp-search-input" placeholder="Search extensions..." class="mp-search-input" />
        <button id="mp-search-btn" class="mp-search-btn">Search</button>
      </div>
      <div class="marketplace-tabs">
        <button class="mp-tab active" data-tab="featured">Featured</button>
        <button class="mp-tab" data-tab="trending">Trending</button>
        <button class="mp-tab" data-tab="categories">Categories</button>
      </div>
      <div class="marketplace-content" id="mp-content"></div>
    `;
    return el;
  }

  private mount(): void {
    const app = document.getElementById('app');
    if (app) app.appendChild(this.element);

    this.element.querySelectorAll('.mp-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        this.element.querySelectorAll('.mp-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.renderTab((btn as HTMLElement).dataset.tab || 'featured');
      });
    });

    const searchInput = this.element.querySelector('#mp-search-input') as HTMLInputElement;
    const searchBtn = this.element.querySelector('#mp-search-btn');

    if (searchBtn) {
      searchBtn.addEventListener('click', () => this.doSearch(searchInput?.value || ''));
    }
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this.doSearch(searchInput.value);
      });
    }
  }

  async loadData(): Promise<void> {
    try {
      const [featRes, trendRes, catRes, statsRes] = await Promise.all([
        this.ipc.request('marketplace.featured', {}),
        this.ipc.request('marketplace.trending', {}),
        this.ipc.request('marketplace.categories', {}),
        this.ipc.request('marketplace.stats', {}),
      ]);
      this.featured = (featRes as any)?.featured || [];
      this.trending = (trendRes as any)?.trending || [];
      this.categories = (catRes as any)?.categories || [];
      this.stats = (statsRes as any) || {};

      const statsEl = this.element.querySelector('#mp-stats');
      if (statsEl) {
        statsEl.innerHTML = `
          <span class="mp-stat">${this.stats.total_plugins || 0} extensions</span>
          <span class="mp-stat">${(this.stats.total_downloads || 0).toLocaleString()} downloads</span>
          <span class="mp-stat">${this.stats.categories || 0} categories</span>
        `;
      }

      this.renderTab('featured');
    } catch (e) {
      console.error('Failed to load marketplace:', e);
    }
  }

  private async doSearch(query: string): Promise<void> {
    try {
      const res = await this.ipc.request('marketplace.search', { query });
      this.searchResults = (res as any)?.results || [];
      this.renderPlugins(this.searchResults);
    } catch (e) {
      console.error('Search failed:', e);
    }
  }

  private renderTab(tab: string): void {
    const content = this.element.querySelector('#mp-content');
    if (!content) return;

    if (tab === 'featured') {
      this.renderPlugins(this.featured, 'Featured Extensions');
    } else if (tab === 'trending') {
      this.renderPlugins(this.trending, 'Trending Extensions');
    } else if (tab === 'categories') {
      this.renderCategories(content);
    }
  }

  private renderPlugins(plugins: any[], title?: string): void {
    const content = this.element.querySelector('#mp-content');
    if (!content) return;

    if (plugins.length === 0) {
      content.innerHTML = `<div class="plugin-empty"><p>No extensions found</p></div>`;
      return;
    }

    content.innerHTML = `
      ${title ? `<h3 class="mp-section-title">${title}</h3>` : ''}
      <div class="mp-grid">
        ${plugins.map(p => `
          <div class="mp-card">
            <div class="mp-card-top">
              <span class="mp-card-icon">${p.icon || '📦'}</span>
              <span class="mp-card-category">${p.category || ''}</span>
            </div>
            <h4 class="mp-card-name">${p.name}</h4>
            <p class="mp-card-desc">${p.description}</p>
            <div class="mp-card-tags">
              ${(p.tags || []).map((t: string) => `<span class="mp-tag">${t}</span>`).join('')}
            </div>
            <div class="mp-card-footer">
              <div class="mp-card-stats">
                <span class="mp-rating">★ ${(p.rating || 0).toFixed(1)}</span>
                <span class="mp-downloads">${(p.downloads || 0).toLocaleString()} dl</span>
              </div>
              <button class="mp-install-btn" data-install="${p.name}" data-version="${p.version}">Install</button>
            </div>
            <span class="mp-card-author">by ${p.author}</span>
          </div>
        `).join('')}
      </div>
    `;

    content.querySelectorAll('.mp-install-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const target = e.target as HTMLElement;
        const name = target.getAttribute('data-install');
        const version = target.getAttribute('data-version');
        if (name) {
          const plugin = plugins.find(p => p.name === name);
          await this.ipc.request('plugins.install', { name, version: version || 'latest', manifest: plugin });
          target.textContent = 'Installed ✓';
          (target as HTMLButtonElement).disabled = true;
        }
      });
    });
  }

  private renderCategories(container: Element): void {
    container.innerHTML = `
      <h3 class="mp-section-title">Categories</h3>
      <div class="mp-categories">
        ${this.categories.map(c => `
          <div class="mp-category-card" data-category="${c.name}">
            <span class="mp-cat-icon">${this.getCategoryIcon(c.name)}</span>
            <span class="mp-cat-name">${c.name}</span>
            <span class="mp-cat-count">${c.count} extensions</span>
          </div>
        `).join('')}
      </div>
    `;

    container.querySelectorAll('.mp-category-card').forEach(card => {
      card.addEventListener('click', async () => {
        const category = (card as HTMLElement).getAttribute('data-category');
        if (category) {
          const res = await this.ipc.request('marketplace.search', { category });
          this.renderPlugins((res as any)?.results || [], `${category} Extensions`);
        }
      });
    });
  }

  private getCategoryIcon(cat: string): string {
    const icons: Record<string, string> = {
      security: '🛡️', coding: '💻', system: '⚙️',
      internet: '🌐', voice: '🎤', other: '📦',
    };
    return icons[cat] || '📦';
  }

  show(): void { this.element.classList.remove('hidden'); }
  hide(): void { this.element.classList.add('hidden'); }
  isVisible(): boolean { return !this.element.classList.contains('hidden'); }
}
