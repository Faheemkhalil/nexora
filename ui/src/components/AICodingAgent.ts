// AICodingAgent Component — AI-powered code assistance panel

import { IPCClient } from '../lib/ipc';

type AgentAction = 'explain' | 'generate' | 'refactor' | 'find_bugs' | 'create_tests';

export class AICodingAgent {
  private element: HTMLElement;
  private ipc: IPCClient;
  private isRunning = false;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'ai-agent';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="ai-agent-header">
        <span class="ai-agent-title">AI Assistant</span>
        <button class="ai-agent-close" title="Close">✕</button>
      </div>
      <div class="ai-agent-actions">
        <button class="ai-action-btn" data-action="explain" title="Explain selected code">
          <span class="ai-action-icon">💡</span>
          <span>Explain</span>
        </button>
        <button class="ai-action-btn" data-action="generate" title="Generate code from description">
          <span class="ai-action-icon">⚡</span>
          <span>Generate</span>
        </button>
        <button class="ai-action-btn" data-action="refactor" title="Refactor code">
          <span class="ai-action-icon">🔧</span>
          <span>Refactor</span>
        </button>
        <button class="ai-action-btn" data-action="find_bugs" title="Find bugs in code">
          <span class="ai-action-icon">🐛</span>
          <span>Find Bugs</span>
        </button>
        <button class="ai-action-btn" data-action="create_tests" title="Create unit tests">
          <span class="ai-action-icon">🧪</span>
          <span>Tests</span>
        </button>
      </div>
      <div class="ai-agent-input-area">
        <textarea class="ai-agent-input" placeholder="Paste code or describe what you need..." rows="6"></textarea>
        <div class="ai-agent-options">
          <select class="ai-lang-select">
            <option value="auto-detect">Auto-detect</option>
            <option value="python">Python</option>
            <option value="typescript">TypeScript</option>
            <option value="javascript">JavaScript</option>
            <option value="rust">Rust</option>
            <option value="go">Go</option>
            <option value="java">Java</option>
            <option value="c">C</option>
            <option value="cpp">C++</option>
          </select>
          <button class="ai-run-btn" disabled>Run</button>
        </div>
      </div>
      <div class="ai-agent-output">
        <div class="ai-output-header">
          <span>Result</span>
          <button class="ai-copy-btn" title="Copy to clipboard">📋</button>
        </div>
        <pre class="ai-output-content">Select an action and provide input.</pre>
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
    // Action buttons
    this.element.querySelectorAll('.ai-action-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.element.querySelectorAll('.ai-action-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const action = (btn as HTMLElement).dataset.action as AgentAction;
        this.onActionSelect(action);
      });
    });

    // Run button
    const runBtn = this.element.querySelector('.ai-run-btn') as HTMLButtonElement;
    const input = this.element.querySelector('.ai-agent-input') as HTMLTextAreaElement;

    input?.addEventListener('input', () => {
      if (runBtn) runBtn.disabled = !input.value.trim() || this.isRunning;
    });

    runBtn?.addEventListener('click', () => this.runAction());

    // Close button
    this.element.querySelector('.ai-agent-close')?.addEventListener('click', () => this.hide());

    // Copy button
    this.element.querySelector('.ai-copy-btn')?.addEventListener('click', () => {
      const content = this.element.querySelector('.ai-output-content')?.textContent || '';
      navigator.clipboard?.writeText(content);
    });
  }

  private currentAction: AgentAction = 'explain';

  private onActionSelect(action: AgentAction): void {
    this.currentAction = action;
    const input = this.element.querySelector('.ai-agent-input') as HTMLTextAreaElement;
    const runBtn = this.element.querySelector('.ai-run-btn') as HTMLButtonElement;

    if (!input) return;

    const placeholders: Record<AgentAction, string> = {
      explain: 'Paste the code you want explained...',
      generate: 'Describe what code to generate (e.g., "a Python function to parse CSV files")...',
      refactor: 'Paste code and describe how to refactor it...',
      find_bugs: 'Paste the code to analyze for bugs...',
      create_tests: 'Paste the code to generate tests for...',
    };

    input.placeholder = placeholders[action] || 'Enter input...';
    input.value = '';
    if (runBtn) runBtn.disabled = true;
    input.focus();
  }

  private async runAction(): Promise<void> {
    if (this.isRunning) return;

    const input = this.element.querySelector('.ai-agent-input') as HTMLTextAreaElement;
    const langSelect = this.element.querySelector('.ai-lang-select') as HTMLSelectElement;
    const runBtn = this.element.querySelector('.ai-run-btn') as HTMLButtonElement;
    const output = this.element.querySelector('.ai-output-content') as HTMLElement;

    if (!input?.value.trim()) return;

    this.isRunning = true;
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.textContent = 'Running...';
    }
    if (output) output.textContent = 'Thinking...';

    const code = input.value.trim();
    const language = langSelect?.value || 'auto-detect';

    try {
      let result: any;

      switch (this.currentAction) {
        case 'explain':
          result = await this.ipc.request('coding.agent.explain', { code, language });
          break;
        case 'generate':
          result = await this.ipc.request('coding.agent.generate', { description: code, language });
          break;
        case 'refactor':
          result = await this.ipc.request('coding.agent.refactor', {
            code, instructions: code, language, confirmed: true,
          });
          break;
        case 'find_bugs':
          result = await this.ipc.request('coding.agent.find_bugs', { code, language });
          break;
        case 'create_tests':
          result = await this.ipc.request('coding.agent.create_tests', { code, language });
          break;
      }

      if (output) {
        if (result?.confirmation_required) {
          output.textContent = '⚠️ Confirmation required by permission system.';
        } else if (result?.explanation) {
          output.textContent = result.explanation;
        } else if (result?.code) {
          output.textContent = result.code;
        } else if (result?.analysis) {
          output.textContent = result.analysis;
        } else if (result?.tests) {
          output.textContent = result.tests;
        } else if (result?.error) {
          output.textContent = `Error: ${result.error}`;
        } else {
          output.textContent = JSON.stringify(result, null, 2);
        }
      }
    } catch (e) {
      if (output) output.textContent = `Error: ${(e as Error).message}`;
    } finally {
      this.isRunning = false;
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.textContent = 'Run';
      }
    }
  }

  show(): void {
    this.element.style.display = 'flex';
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
