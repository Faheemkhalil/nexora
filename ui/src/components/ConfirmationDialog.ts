// ConfirmationDialog Component — tool action confirmation prompts

import type { IPCClient } from '../lib/ipc';

interface ConfirmationRequest {
  token: string;
  tool: string;
  inputs: any;
  resolve: (confirmed: boolean) => void;
}

export class ConfirmationDialog {
  private element: HTMLElement;
  private pending: ConfirmationRequest | null = null;

  constructor(_ipc: IPCClient) {
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'confirm-overlay';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="confirm-dialog">
        <div class="confirm-header">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span>Confirmation Required</span>
        </div>
        <div class="confirm-body">
          <div class="confirm-tool" id="confirm-tool"></div>
          <div class="confirm-details" id="confirm-details"></div>
        </div>
        <div class="confirm-actions">
          <button class="confirm-btn cancel" id="confirm-cancel">Cancel</button>
          <button class="confirm-btn confirm" id="confirm-ok">Confirm</button>
        </div>
      </div>
    `;
    return div;
  }

  private mount(): void {
    document.body.appendChild(this.element);
  }

  private setupListeners(): void {
    this.element.querySelector('#confirm-cancel')?.addEventListener('click', () => {
      this.respond(false);
    });
    this.element.querySelector('#confirm-ok')?.addEventListener('click', () => {
      this.respond(true);
    });
    this.element.addEventListener('click', (e) => {
      if (e.target === this.element) this.respond(false);
    });
  }

  async requestConfirmation(tool: string, inputs: any): Promise<boolean> {
    return new Promise((resolve) => {
      this.pending = { token: '', tool, inputs, resolve };

      const toolEl = this.element.querySelector('#confirm-tool') as HTMLElement;
      const detailsEl = this.element.querySelector('#confirm-details') as HTMLElement;

      toolEl.textContent = `Tool: ${tool}`;
      detailsEl.textContent = JSON.stringify(inputs, null, 2);

      this.element.style.display = 'flex';
    });
  }

  private respond(confirmed: boolean): void {
    this.element.style.display = 'none';
    if (this.pending) {
      this.pending.resolve(confirmed);
      this.pending = null;
    }
  }
}
