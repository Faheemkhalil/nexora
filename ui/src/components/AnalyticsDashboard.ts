// Analytics Dashboard — performance, usage metrics, feature adoption, and health

import { IPCClient } from '../lib/ipc';

export class AnalyticsDashboard {
  private element: HTMLElement;
  private ipc: IPCClient;
  private refreshTimer: number | null = null;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.loadData();
  }

  private createElement(): HTMLElement {
    const el = document.createElement('div');
    el.className = 'analytics-dashboard hidden';
    el.innerHTML = `
      <div class="analytics-header">
        <h2>Analytics Dashboard</h2>
        <div class="analytics-actions">
          <button id="analytics-refresh" class="analytics-btn">Refresh</button>
        </div>
      </div>
      <div id="analytics-content" class="analytics-content">
        <div class="analytics-loading">Loading analytics...</div>
      </div>
    `;
    return el;
  }

  private mount(): void {
    const app = document.getElementById('app');
    if (app) app.appendChild(this.element);

    const refreshBtn = this.element.querySelector('#analytics-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadData());
    }
  }

  async loadData(): Promise<void> {
    const content = this.element.querySelector('#analytics-content');
    if (!content) return;

    try {
      const [dashRes, perfRes, adoptRes] = await Promise.all([
        this.ipc.request('analytics.dashboard', {}),
        this.ipc.request('analytics.performance', {}),
        this.ipc.request('analytics.adoption', {}),
      ]);

      const dash = (dashRes as any) || {};
      const perf = (perfRes as any) || {};
      const adopt = (adoptRes as any) || {};

      content.innerHTML = `
        <div class="analytics-grid">
          ${this.renderHealthScore(dash)}
          ${this.renderPerformance(perf)}
          ${this.renderUsageStats(dash.usage || {})}
          ${this.renderFeatureAdoption(adopt)}
          ${this.renderUpdateInfo()}
        </div>
      `;
    } catch (e) {
      content.innerHTML = `<div class="analytics-error">Failed to load analytics</div>`;
      console.error('Analytics load failed:', e);
    }
  }

  private renderHealthScore(dash: any): string {
    const score = dash.health_score ?? 0;
    const color = score >= 80 ? '#00dfff' : score >= 50 ? '#ffa500' : '#ff4444';
    const label = score >= 80 ? 'Healthy' : score >= 50 ? 'Warning' : 'Critical';
    return `
      <div class="analytics-card analytics-health">
        <h3>System Health</h3>
        <div class="health-score" style="color: ${color}">
          <span class="health-value">${score}</span>
          <span class="health-label">${label}</span>
        </div>
        <div class="health-bar">
          <div class="health-fill" style="width: ${score}%; background: ${color}"></div>
        </div>
      </div>
    `;
  }

  private renderPerformance(perf: any): string {
    const proc = perf.process || {};
    const sys = perf.system || {};
    return `
      <div class="analytics-card">
        <h3>Performance</h3>
        <div class="analytics-metrics">
          <div class="metric">
            <span class="metric-label">Memory</span>
            <span class="metric-value">${proc.memory_mb || 0} MB</span>
          </div>
          <div class="metric">
            <span class="metric-label">CPU</span>
            <span class="metric-value">${proc.cpu_percent || 0}%</span>
          </div>
          <div class="metric">
            <span class="metric-label">Threads</span>
            <span class="metric-value">${proc.threads || 0}</span>
          </div>
          <div class="metric">
            <span class="metric-label">Uptime</span>
            <span class="metric-value">${this.formatUptime(proc.uptime_seconds || 0)}</span>
          </div>
          <div class="metric">
            <span class="metric-label">System RAM</span>
            <span class="metric-value">${sys.memory_used_gb || 0}/${sys.memory_total_gb || 0} GB</span>
          </div>
          <div class="metric">
            <span class="metric-label">System CPU</span>
            <span class="metric-value">${sys.cpu_percent || 0}%</span>
          </div>
        </div>
      </div>
    `;
  }

  private renderUsageStats(usage: any): string {
    const byType = usage.events_by_type || {};
    const entries = Object.entries(byType).slice(0, 8);
    return `
      <div class="analytics-card">
        <h3>Usage Statistics</h3>
        <div class="analytics-metrics">
          <div class="metric">
            <span class="metric-label">Total Events</span>
            <span class="metric-value">${usage.total_events || 0}</span>
          </div>
          <div class="metric">
            <span class="metric-label">Sessions</span>
            <span class="metric-value">${usage.total_sessions || 0}</span>
          </div>
        </div>
        ${entries.length > 0 ? `
          <div class="analytics-chart">
            ${entries.map(([type, count]) => `
              <div class="chart-bar-row">
                <span class="chart-label">${type}</span>
                <div class="chart-bar" style="width: ${Math.min(100, ((count as number) / Math.max(1, ...Object.values(byType) as number[])) * 100)}%"></div>
                <span class="chart-count">${count}</span>
              </div>
            `).join('')}
          </div>
        ` : '<p class="analytics-empty">No events recorded yet</p>'}
      </div>
    `;
  }

  private renderFeatureAdoption(adopt: any): string {
    const features = adopt.features || [];
    return `
      <div class="analytics-card">
        <h3>Feature Adoption</h3>
        ${features.length > 0 ? `
          <div class="analytics-chart">
            ${features.map((f: any) => `
              <div class="chart-bar-row">
                <span class="chart-label">${f.name}</span>
                <div class="chart-bar" style="width: ${Math.min(100, (f.usage_count / Math.max(1, ...features.map((x: any) => x.usage_count))) * 100)}%"></div>
                <span class="chart-count">${f.usage_count}</span>
              </div>
            `).join('')}
          </div>
        ` : '<p class="analytics-empty">No feature data yet</p>'}
      </div>
    `;
  }

  private renderUpdateInfo(): string {
    return `
      <div class="analytics-card analytics-update-card">
        <h3>System</h3>
        <div class="analytics-metrics">
          <div class="metric">
            <span class="metric-label">Version</span>
            <span class="metric-value">v0.9.0</span>
          </div>
          <div class="metric">
            <span class="metric-label">Auto-update</span>
            <span class="metric-value" style="color: var(--accent)">Enabled</span>
          </div>
          <div class="metric">
            <span class="metric-label">Platform</span>
            <span class="metric-value">${navigator.platform}</span>
          </div>
        </div>
      </div>
    `;
  }

  private formatUptime(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
    return `${Math.round(seconds / 86400)}d`;
  }

  show(): void {
    this.element.classList.remove('hidden');
    this.loadData();
    this.refreshTimer = window.setInterval(() => this.loadData(), 10000);
  }

  hide(): void {
    this.element.classList.add('hidden');
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  isVisible(): boolean { return !this.element.classList.contains('hidden'); }
}
