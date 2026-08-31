// GitPanel Component — git status, diff, log, commit, branch operations

import { IPCClient } from '../lib/ipc';

interface GitFile {
  path: string;
  index_status: string;
  work_status: string;
  staged: boolean;
  modified: boolean;
}

interface GitCommit {
  hash: string;
  short_hash: string;
  message: string;
  author: string;
  date: string;
}

interface GitBranch {
  name: string;
  current: boolean;
}

type GitView = 'status' | 'log' | 'branches';

export class GitPanel {
  private element: HTMLElement;
  private ipc: IPCClient;
  private projectPath: string = '';
  private currentView: GitView = 'status';
  private files: GitFile[] = [];
  private commits: GitCommit[] = [];
  private branches: GitBranch[] = [];
  private currentBranch: string = '';

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'git-panel';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="git-header">
        <span class="git-title">Git</span>
        <div class="git-branch-badge">—</div>
      </div>
      <div class="git-tabs">
        <button class="git-tab active" data-view="status">Changes</button>
        <button class="git-tab" data-view="log">History</button>
        <button class="git-tab" data-view="branches">Branches</button>
      </div>
      <div class="git-content">
        <div class="git-status-view">
          <div class="git-files"></div>
          <div class="git-commit-box">
            <input type="text" class="git-commit-input" placeholder="Commit message..." />
            <button class="git-commit-btn" disabled>Commit</button>
          </div>
        </div>
        <div class="git-log-view" style="display:none"></div>
        <div class="git-branches-view" style="display:none"></div>
      </div>
    `;
    return div;
  }

  private mount(): void {
    const rightPanel = document.querySelector('.rightpanel');
    if (rightPanel) {
      rightPanel.appendChild(this.element);
    }

    // Tab switching
    this.element.querySelectorAll('.git-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const view = (tab as HTMLElement).dataset.view as GitView;
        this.switchView(view);
      });
    });
  }

  setProject(path: string): void {
    this.projectPath = path;
    this.refresh();
  }

  async refresh(): Promise<void> {
    if (!this.projectPath) return;

    try {
      // Fetch git status
      const statusResult = await this.ipc.request('coding.git.status', { path: this.projectPath });
      this.files = statusResult.files || [];
      this.currentBranch = statusResult.branch || 'unknown';

      const badge = this.element.querySelector('.git-branch-badge');
      if (badge) badge.textContent = this.currentBranch;

      this.renderCurrentView();
    } catch (e) {
      console.warn('Git refresh failed:', e);
    }
  }

  private async switchView(view: GitView): Promise<void> {
    this.currentView = view;

    this.element.querySelectorAll('.git-tab').forEach((tab) => {
      tab.classList.toggle('active', (tab as HTMLElement).dataset.view === view);
    });

    // Hide all views
    const statusView = this.element.querySelector('.git-status-view') as HTMLElement;
    const logView = this.element.querySelector('.git-log-view') as HTMLElement;
    const branchesView = this.element.querySelector('.git-branches-view') as HTMLElement;
    if (statusView) statusView.style.display = 'none';
    if (logView) logView.style.display = 'none';
    if (branchesView) branchesView.style.display = 'none';

    if (view === 'status') {
      if (statusView) statusView.style.display = 'block';
    } else if (view === 'log') {
      if (logView) logView.style.display = 'block';
      await this.loadLog();
    } else if (view === 'branches') {
      if (branchesView) branchesView.style.display = 'block';
      await this.loadBranches();
    }
  }

  private renderCurrentView(): void {
    if (this.currentView === 'status') {
      this.renderStatus();
    }
  }

  private renderStatus(): void {
    const filesContainer = this.element.querySelector('.git-files') as HTMLElement;
    if (!filesContainer) return;

    if (this.files.length === 0) {
      filesContainer.innerHTML = '<div class="git-empty">No changes — working tree clean</div>';
      return;
    }

    filesContainer.innerHTML = this.files.map(f => `
      <div class="git-file" data-path="${f.path}">
        <span class="git-file-status" title="${f.index_status}/${f.work_status}">
          ${this.statusIcon(f)}
        </span>
        <span class="git-file-path">${f.path}</span>
      </div>
    `).join('');

    // Update commit button
    const commitBtn = this.element.querySelector('.git-commit-btn') as HTMLButtonElement;
    if (commitBtn) {
      const staged = this.files.filter(f => f.staged).length;
      commitBtn.disabled = staged === 0;
      commitBtn.textContent = staged > 0 ? `Commit (${staged})` : 'Commit';
    }
  }

  private statusIcon(f: GitFile): string {
    if (f.index_status === 'A') return '🟢'; // Added
    if (f.index_status === 'M' || f.work_status === 'M') return '🟡'; // Modified
    if (f.index_status === 'D' || f.work_status === 'D') return '🔴'; // Deleted
    if (f.index_status === '?') return '⚪'; // Untracked
    return '🔵';
  }

  private async loadLog(): Promise<void> {
    if (!this.projectPath) return;

    try {
      const result = await this.ipc.request('coding.git.log', { path: this.projectPath, count: 30 });
      this.commits = result.commits || [];

      const logView = this.element.querySelector('.git-log-view') as HTMLElement;
      if (!logView) return;

      logView.innerHTML = this.commits.map(c => `
        <div class="git-commit-entry">
          <span class="git-commit-hash">${c.short_hash}</span>
          <span class="git-commit-msg">${c.message}</span>
          <span class="git-commit-date">${new Date(c.date).toLocaleDateString()}</span>
        </div>
      `).join('') || '<div class="git-empty">No commits found</div>';
    } catch (e) {
      console.warn('Git log failed:', e);
    }
  }

  private async loadBranches(): Promise<void> {
    if (!this.projectPath) return;

    try {
      const result = await this.ipc.request('coding.git.branch', { path: this.projectPath, action: 'list' });
      this.branches = result.branches || [];
      this.currentBranch = result.current || '';

      const branchesView = this.element.querySelector('.git-branches-view') as HTMLElement;
      if (!branchesView) return;

      branchesView.innerHTML = this.branches.map(b => `
        <div class="git-branch-entry ${b.current ? 'current' : ''}">
          <span class="git-branch-icon">${b.current ? '●' : '○'}</span>
          <span class="git-branch-name">${b.name}</span>
        </div>
      `).join('') || '<div class="git-empty">No branches found</div>';
    } catch (e) {
      console.warn('Git branches failed:', e);
    }
  }

  async commit(message: string): Promise<void> {
    if (!this.projectPath || !message.trim()) return;

    try {
      // Stage all files first
      await this.ipc.request('coding.git.add', { path: this.projectPath, files: ['*'] });

      // Commit
      const result = await this.ipc.request('coding.git.commit', {
        path: this.projectPath,
        message: message.trim(),
        confirmed: true,
      });

      if (result.success) {
        // Clear input
        const input = this.element.querySelector('.git-commit-input') as HTMLInputElement;
        if (input) input.value = '';
      }

      await this.refresh();
    } catch (e) {
      console.warn('Git commit failed:', e);
    }
  }

  show(): void {
    this.element.style.display = 'block';
    this.refresh();
  }

  hide(): void {
    this.element.style.display = 'none';
  }
}
