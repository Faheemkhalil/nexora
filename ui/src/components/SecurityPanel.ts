// SecurityPanel Component — findings dashboard, lab management, reports, scope

import { IPCClient } from '../lib/ipc';

interface Finding {
  id: string;
  title: string;
  severity: string;
  affected_asset: string;
  description: string;
  status: string;
  category: string;
  created_at: number;
}

interface Lab {
  id: string;
  name: string;
  target: string;
  scope: string;
  status: string;
  findings_count: number;
}

type SecurityTab = 'dashboard' | 'findings' | 'labs' | 'reports';

export class SecurityPanel {
  private element: HTMLElement;
  private ipc: IPCClient;
  private findings: Finding[] = [];
  private labs: Lab[] = [];
  private summary: any = {};
  private currentTab: SecurityTab = 'dashboard';

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'security-panel';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="sec-header">
        <span class="sec-title">🛡️ Security</span>
      </div>
      <div class="sec-tabs">
        <button class="sec-tab active" data-tab="dashboard">📊 Dashboard</button>
        <button class="sec-tab" data-tab="findings">🔍 Findings</button>
        <button class="sec-tab" data-tab="labs">🔬 Labs</button>
        <button class="sec-tab" data-tab="reports">📄 Reports</button>
      </div>
      <div class="sec-content">
        <div class="sec-dashboard"></div>
        <div class="sec-findings" style="display:none"></div>
        <div class="sec-labs" style="display:none"></div>
        <div class="sec-reports" style="display:none"></div>
      </div>
    `;
    return div;
  }

  private mount(): void {
    const main = document.querySelector('.main');
    if (main) main.appendChild(this.element);
  }

  private setupListeners(): void {
    this.element.querySelectorAll('.sec-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const t = (tab as HTMLElement).dataset.tab as SecurityTab;
        this.switchTab(t);
      });
    });
  }

  private switchTab(tab: SecurityTab): void {
    this.currentTab = tab;
    this.element.querySelectorAll('.sec-tab').forEach(t => {
      t.classList.toggle('active', (t as HTMLElement).dataset.tab === tab);
    });
    const panels = ['dashboard', 'findings', 'labs', 'reports'];
    panels.forEach(p => {
      const el = this.element.querySelector(`.sec-${p}`) as HTMLElement;
      if (el) el.style.display = p === tab ? 'block' : 'none';
    });
    this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      const [findingsRes, summaryRes, labsRes] = await Promise.all([
        this.ipc.request('security.findings.list', {}),
        this.ipc.request('security.findings.summary', {}),
        this.ipc.request('security.lab.status', {}),
      ]);
      this.findings = findingsRes.findings || [];
      this.summary = summaryRes;
      this.labs = labsRes.labs || [];
      this.renderCurrentTab();
    } catch (e) {
      console.warn('Security refresh failed:', e);
    }
  }

  private renderCurrentTab(): void {
    if (this.currentTab === 'dashboard') this.renderDashboard();
    else if (this.currentTab === 'findings') this.renderFindings();
    else if (this.currentTab === 'labs') this.renderLabs();
    else if (this.currentTab === 'reports') this.renderReports();
  }

  private renderDashboard(): void {
    const el = this.element.querySelector('.sec-dashboard') as HTMLElement;
    if (!el) return;
    const s = this.summary;
    el.innerHTML = `
      <div class="sec-stats">
        <div class="sec-stat critical"><div class="sec-stat-num">${s.critical || 0}</div><div>Critical</div></div>
        <div class="sec-stat high"><div class="sec-stat-num">${s.high || 0}</div><div>High</div></div>
        <div class="sec-stat medium"><div class="sec-stat-num">${s.medium || 0}</div><div>Medium</div></div>
        <div class="sec-stat low"><div class="sec-stat-num">${s.low || 0}</div><div>Low</div></div>
        <div class="sec-stat info"><div class="sec-stat-num">${s.info || 0}</div><div>Info</div></div>
      </div>
      <div class="sec-summary-text">Total: ${s.total || 0} findings across ${this.labs.length} lab(s)</div>
    `;
  }

  private renderFindings(): void {
    const el = this.element.querySelector('.sec-findings') as HTMLElement;
    if (!el) return;
    if (this.findings.length === 0) {
      el.innerHTML = '<div class="sec-empty">No findings yet. Create one from the AI chat or tools.</div>';
      return;
    }
    el.innerHTML = this.findings.map(f => `
      <div class="sec-finding sev-${f.severity}">
        <div class="sec-finding-header">
          <span class="sev-badge ${f.severity}">${f.severity.toUpperCase()}</span>
          <span class="sec-finding-title">${f.title}</span>
          <span class="sec-finding-status">${f.status}</span>
        </div>
        <div class="sec-finding-meta">${f.affected_asset || 'N/A'} · ${f.category}</div>
      </div>
    `).join('');
  }

  private renderLabs(): void {
    const el = this.element.querySelector('.sec-labs') as HTMLElement;
    if (!el) return;
    if (this.labs.length === 0) {
      el.innerHTML = '<div class="sec-empty">No labs configured. Create one to start an assessment.</div>';
      return;
    }
    el.innerHTML = this.labs.map(l => `
      <div class="sec-lab status-${l.status}">
        <div class="sec-lab-header">
          <span class="sec-lab-name">${l.name}</span>
          <span class="sec-lab-status">${l.status}</span>
        </div>
        <div class="sec-lab-meta">Target: ${l.target} · Findings: ${l.findings_count}</div>
      </div>
    `).join('');
  }

  private renderReports(): void {
    const el = this.element.querySelector('.sec-reports') as HTMLElement;
    if (!el) return;
    el.innerHTML = `
      <div class="sec-report-actions">
        <button class="sec-btn" id="gen-md-report">📄 Generate Markdown Report</button>
        <button class="sec-btn" id="gen-html-report">🌐 Generate HTML Report</button>
      </div>
      <div class="sec-report-output" style="display:none"></div>
    `;
    el.querySelector('#gen-md-report')?.addEventListener('click', () => this.generateReport('markdown'));
    el.querySelector('#gen-html-report')?.addEventListener('click', () => this.generateReport('html'));
  }

  private async generateReport(format: string): Promise<void> {
    const output = this.element.querySelector('.sec-report-output') as HTMLElement;
    if (output) output.style.display = 'block';
    try {
      const result = await this.ipc.request('security.reports.generate', { format });
      if (output) {
        output.innerHTML = `<pre class="sec-report-pre">${result.report || 'No report generated'}</pre>`;
      }
    } catch (e) {
      if (output) output.textContent = `Error: ${(e as Error).message}`;
    }
  }

  show(): void {
    this.element.style.display = 'flex';
    this.refresh();
  }

  hide(): void {
    this.element.style.display = 'none';
  }
}
