// Diagnostics Modal

import { IPCClient } from '../lib/ipc';

interface DiagnosticResult {
  name: string;
  status: 'ok' | 'warning' | 'error';
  details: string;
  remediation: string | null;
}

export class DiagnosticsModal {
  private element: HTMLElement | null = null;
  private ipc: IPCClient;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
  }

  open(): void {
    if (!this.element) {
      this.createElement();
    }
    this.element!.classList.add('open');
    document.body.style.overflow = 'hidden';
    this.runDiagnostics();
  }

  close(): void {
    this.element?.classList.remove('open');
    document.body.style.overflow = '';
  }

  private createElement(): void {
    this.element = document.createElement('div');
    this.element.className = 'modal-overlay';
    this.element.innerHTML = `
      <div class="modal" style="max-width: 800px;">
        <div class="modal-header">
          <h2 class="modal-title">System Diagnostics</h2>
          <button class="modal-close" aria-label="Close">&times;</button>
        </div>
        <div class="modal-content">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span id="diag-summary">Running diagnostics...</span>
            <button class="chat-send" id="rerun-diag">Run Again</button>
          </div>
          <div class="diagnostics-list" id="diag-list"></div>
        </div>
      </div>
    `;

    document.body.appendChild(this.element);

    this.element.querySelector('.modal-close')?.addEventListener('click', () => this.close());
    this.element.addEventListener('click', (e) => {
      if (e.target === this.element) this.close();
    });

    this.element.querySelector('#rerun-diag')?.addEventListener('click', () => this.runDiagnostics());
  }

  private async runDiagnostics(): Promise<void> {
    const listEl = this.element!.querySelector('#diag-list') as HTMLElement;
    const summaryEl = this.element!.querySelector('#diag-summary') as HTMLElement;
    const btn = this.element!.querySelector('#rerun-diag') as HTMLButtonElement;

    btn.disabled = true;
    btn.textContent = 'Running...';
    listEl.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--fg-muted);">Running diagnostics...</div>';

    try {
      const results: DiagnosticResult[] = await this.ipc.runDiagnostics();
      this.renderResults(results);
      const ok = results.filter(r => r.status === 'ok').length;
      const warn = results.filter(r => r.status === 'warning').length;
      const err = results.filter(r => r.status === 'error').length;
      summaryEl.textContent = `${ok} OK • ${warn} Warnings • ${err} Errors`;
    } catch (e) {
      listEl.innerHTML = `<div style="color: var(--accent-error); padding: 20px;">Failed to run diagnostics: ${(e as Error).message}</div>`;
      summaryEl.textContent = 'Error';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run Again';
    }
  }

  private renderResults(results: DiagnosticResult[]): void {
    const listEl = this.element!.querySelector('#diag-list') as HTMLElement;
    listEl.innerHTML = results.map(r => `
      <div class="diagnostic-item ${r.status}">
        <div class="diagnostic-icon">
          ${this.getStatusIcon(r.status)}
        </div>
        <div class="diagnostic-info">
          <div class="diagnostic-name">${r.name}</div>
          <div class="diagnostic-details">${r.details}</div>
          ${r.remediation ? `<div class="diagnostic-remediation">${r.remediation}</div>` : ''}
        </div>
      </div>
    `).join('');
  }

  private getStatusIcon(status: string): string {
    switch (status) {
      case 'ok':
        return `<svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-secondary)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`;
      case 'warning':
        return `<svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-warning)" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
      case 'error':
        return `<svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-error)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
      default:
        return '';
    }
  }
}