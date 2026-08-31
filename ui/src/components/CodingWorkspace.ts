// CodingWorkspace — unified coding workspace combining editor, git, AI agent, and test runner

import { IPCClient } from '../lib/ipc';
import { CodeEditor } from './CodeEditor';
import { GitPanel } from './GitPanel';
import { AICodingAgent } from './AICodingAgent';

type WorkspaceTab = 'editor' | 'git' | 'ai' | 'tests';

export class CodingWorkspace {
  private element: HTMLElement;
  private ipc: IPCClient;
  private editor: CodeEditor;
  private gitPanel: GitPanel;
  private aiAgent: AICodingAgent;
  private projectPath: string = '';

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.editor = new CodeEditor(ipc);
    this.gitPanel = new GitPanel(ipc);
    this.aiAgent = new AICodingAgent(ipc);
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'coding-workspace';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="coding-toolbar">
        <div class="coding-tabs">
          <button class="coding-tab active" data-tab="editor">📝 Editor</button>
          <button class="coding-tab" data-tab="git">🔀 Git</button>
          <button class="coding-tab" data-tab="ai">🤖 AI</button>
          <button class="coding-tab" data-tab="tests">🧪 Tests</button>
        </div>
        <div class="coding-project">
          <input type="text" class="coding-project-input" placeholder="Project path..." />
          <button class="coding-project-btn">Open</button>
        </div>
      </div>
      <div class="coding-content">
        <div class="coding-editor-area"></div>
        <div class="coding-test-panel" style="display:none">
          <div class="test-header">
            <span class="test-title">Test Runner</span>
            <select class="test-framework">
              <option value="auto">Auto-detect</option>
              <option value="pytest">pytest</option>
              <option value="npm">npm test</option>
              <option value="cargo">cargo test</option>
            </select>
            <button class="test-run-btn">▶ Run Tests</button>
          </div>
          <div class="test-output"></div>
        </div>
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
    // Tab switching
    this.element.querySelectorAll('.coding-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const t = (tab as HTMLElement).dataset.tab as WorkspaceTab;
        this.switchTab(t);
      });
    });

    // Project open
    const projectBtn = this.element.querySelector('.coding-project-btn');
    const projectInput = this.element.querySelector('.coding-project-input') as HTMLInputElement;

    projectBtn?.addEventListener('click', () => {
      const path = projectInput?.value?.trim();
      if (path) {
        this.projectPath = path;
        this.gitPanel.setProject(path);
      }
    });

    projectInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const path = projectInput.value.trim();
        if (path) {
          this.projectPath = path;
          this.gitPanel.setProject(path);
        }
      }
    });

    // Test runner
    const testRunBtn = this.element.querySelector('.test-run-btn');
    testRunBtn?.addEventListener('click', () => this.runTests());

    // Git commit
    const commitInput = this.element.querySelector('.git-commit-input') as HTMLInputElement;
    const commitBtn = this.element.querySelector('.git-commit-btn');

    commitBtn?.addEventListener('click', () => {
      const msg = commitInput?.value?.trim();
      if (msg && this.projectPath) {
        this.gitPanel.commit(msg);
      }
    });

    commitInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const msg = commitInput.value.trim();
        if (msg && this.projectPath) {
          this.gitPanel.commit(msg);
        }
      }
    });
  }

  private switchTab(tab: WorkspaceTab): void {
    // Update tab UI
    this.element.querySelectorAll('.coding-tab').forEach(t => {
      t.classList.toggle('active', (t as HTMLElement).dataset.tab === tab);
    });

    // Show/hide sub-components
    if (tab === 'editor') {
      this.editor.show();
      this.gitPanel.hide();
      this.aiAgent.hide();
      this.showTestPanel(false);
    } else if (tab === 'git') {
      this.editor.hide();
      this.gitPanel.show();
      this.aiAgent.hide();
      this.showTestPanel(false);
    } else if (tab === 'ai') {
      this.editor.hide();
      this.gitPanel.hide();
      this.aiAgent.show();
      this.showTestPanel(false);
    } else if (tab === 'tests') {
      this.editor.hide();
      this.gitPanel.hide();
      this.aiAgent.hide();
      this.showTestPanel(true);
    }
  }

  private showTestPanel(show: boolean): void {
    const testPanel = this.element.querySelector('.coding-test-panel') as HTMLElement;
    if (testPanel) testPanel.style.display = show ? 'flex' : 'none';
  }

  private async runTests(): Promise<void> {
    if (!this.projectPath) return;

    const framework = (this.element.querySelector('.test-framework') as HTMLSelectElement)?.value || 'auto';
    const output = this.element.querySelector('.test-output') as HTMLElement;
    const runBtn = this.element.querySelector('.test-run-btn') as HTMLButtonElement;

    if (runBtn) {
      runBtn.disabled = true;
      runBtn.textContent = '⏳ Running...';
    }
    if (output) output.textContent = 'Running tests...';

    try {
      const result = await this.ipc.request('coding.test.run', {
        path: this.projectPath,
        framework,
        verbose: true,
      });

      if (output) {
        const status = result.exit_code === 0 ? '✅ PASSED' : '❌ FAILED';
        let text = `${status} (exit ${result.exit_code})\n`;
        text += `Framework: ${result.framework}\n`;
        text += `Time: ${(result.elapsed_ms / 1000).toFixed(1)}s\n`;
        text += `Total: ${result.total} | Passed: ${result.passed} | Failed: ${result.failed} | Skipped: ${result.skipped}\n`;
        text += '\n--- Output ---\n';
        text += result.stdout || '';
        if (result.stderr) {
          text += '\n--- Errors ---\n' + result.stderr;
        }
        output.textContent = text;
      }
    } catch (e) {
      if (output) output.textContent = `Error: ${(e as Error).message}`;
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.textContent = '▶ Run Tests';
      }
    }
  }

  openFile(path: string): void {
    this.switchTab('editor');
    this.editor.openFile(path);
  }

  show(): void {
    this.element.style.display = 'flex';
    this.editor.show();
  }

  hide(): void {
    this.element.style.display = 'none';
    this.editor.hide();
    this.gitPanel.hide();
    this.aiAgent.hide();
  }

  toggle(): void {
    if (this.element.style.display === 'none') {
      this.show();
    } else {
      this.hide();
    }
  }
}
