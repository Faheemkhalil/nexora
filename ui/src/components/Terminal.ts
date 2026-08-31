// Terminal Component — command input, output display, session management

import { IPCClient } from '../lib/ipc';

interface TerminalEntry {
  command: string;
  output: string;
  exitCode: number;
  timestamp: number;
}

export class Terminal {
  private element: HTMLElement;
  private ipc: IPCClient;
  private history: TerminalEntry[] = [];
  private commandHistory: string[] = [];
  private historyIndex = -1;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'terminal-container';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="terminal-header">
        <span class="terminal-title">Terminal</span>
        <div class="terminal-actions">
          <button class="terminal-action" id="terminal-clear" title="Clear">Clear</button>
        </div>
      </div>
      <div class="terminal-output"></div>
      <div class="terminal-input-row">
        <span class="terminal-prompt">$</span>
        <input type="text" class="terminal-input" placeholder="Enter command..." autocomplete="off" spellcheck="false" />
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
    const input = this.element.querySelector('.terminal-input') as HTMLInputElement;
    const clearBtn = this.element.querySelector('#terminal-clear');

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && input.value.trim()) {
        e.preventDefault();
        this.executeCommand(input.value.trim());
        this.commandHistory.push(input.value.trim());
        this.historyIndex = this.commandHistory.length;
        input.value = '';
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (this.historyIndex > 0) {
          this.historyIndex--;
          input.value = this.commandHistory[this.historyIndex] || '';
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (this.historyIndex < this.commandHistory.length - 1) {
          this.historyIndex++;
          input.value = this.commandHistory[this.historyIndex] || '';
        } else {
          this.historyIndex = this.commandHistory.length;
          input.value = '';
        }
      }
    });

    clearBtn?.addEventListener('click', () => this.clear());
  }

  private async executeCommand(command: string): Promise<void> {
    this.appendOutput(`$ ${command}\n`, 'command');

    try {
      const result = await this.ipc.request('tools.execute', {
        name: 'terminal.execute',
        inputs: { command, timeout: 30 },
        confirmed: true,
      });

      if (result.confirmation_required) {
        this.appendOutput(`[Confirmation required] Token: ${result.token}\n`, 'warning');
        return;
      }

      const entry: TerminalEntry = {
        command,
        output: (result.stdout || '') + (result.stderr ? `\n${result.stderr}` : ''),
        exitCode: result.exit_code ?? -1,
        timestamp: Date.now(),
      };

      this.history.push(entry);

      if (result.stdout) {
        this.appendOutput(result.stdout, 'stdout');
      }
      if (result.stderr) {
        this.appendOutput(result.stderr, 'stderr');
      }
      if (result.exit_code !== 0 && result.exit_code !== undefined) {
        this.appendOutput(`[exit ${result.exit_code}]\n`, 'error');
      }
    } catch (e) {
      this.appendOutput(`Error: ${(e as Error).message}\n`, 'error');
    }
  }

  private appendOutput(text: string, type: string = ''): void {
    const output = this.element.querySelector('.terminal-output') as HTMLElement;
    const span = document.createElement('span');
    span.className = `terminal-line ${type}`;
    span.textContent = text;
    output.appendChild(span);
    output.scrollTop = output.scrollHeight;
  }

  clear(): void {
    const output = this.element.querySelector('.terminal-output') as HTMLElement;
    output.innerHTML = '';
    this.history = [];
  }

  show(): void {
    this.element.style.display = 'flex';
    const input = this.element.querySelector('.terminal-input') as HTMLInputElement;
    input?.focus();
  }

  hide(): void {
    this.element.style.display = 'none';
  }

  toggle(): void {
    if (this.element.style.display === 'none') {
      this.show();
    } else {
      this.hide();
    }
  }
}
