// Sidebar Navigation Component

import { IPCClient } from '../lib/ipc';

const homeIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`;
const chatIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
const voiceIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="19" x2="8" y2="22"/><line x1="16" y1="19" x2="16" y2="22"/></svg>`;
const codeIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
const folderIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`;
const browserIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;
const terminalIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`;
const shieldIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`;
const fileIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
const settingsIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82-.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`;
const activityIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`;

const NAV_ITEMS = [
  { id: 'home', label: 'Home', icon: homeIcon },
  { id: 'chat', label: 'Chat', icon: chatIcon },
  { id: 'voice', label: 'Voice', icon: voiceIcon },
  { id: 'coding', label: 'Coding', icon: codeIcon },
  { id: 'projects', label: 'Projects', icon: folderIcon },
  { id: 'browser', label: 'Browser', icon: browserIcon },
  { id: 'terminal', label: 'Terminal', icon: terminalIcon },
  { id: 'security', label: 'Security', icon: shieldIcon },
  { id: 'reports', label: 'Reports', icon: fileIcon },
  { id: 'settings', label: 'Settings', icon: settingsIcon },
  { id: 'diagnostics', label: 'Diagnostics', icon: activityIcon },
];

export class Sidebar {
  private element: HTMLElement;
  private onNavigate: (view: string) => void;
  private activeView = 'chat';

  constructor(_ipc: IPCClient, onNavigate: (view: string) => void) {
    this.onNavigate = onNavigate;
    this.element = this.createElement();
    this.mount();
  }

  private createElement(): HTMLElement {
    const sidebar = document.createElement('aside');
    sidebar.className = 'sidebar';
    sidebar.innerHTML = `
      <div class="sidebar-section">
        <div class="sidebar-title">Navigation</div>
        <nav class="nav-list"></nav>
      </div>
      <div class="sidebar-section">
        <div class="sidebar-title">System</div>
        <nav class="nav-list system-nav"></nav>
      </div>
    `;
    return sidebar;
  }

  private mount(): void {
    const app = document.getElementById('app');
    if (app) {
      app.insertBefore(this.element, app.firstChild);
    }
    this.renderNav();
  }

  private renderNav(): void {
    const navList = this.element.querySelector('.nav-list') as HTMLElement;
    const systemNav = this.element.querySelector('.system-nav') as HTMLElement;

    NAV_ITEMS.forEach((item) => {
      const btn = document.createElement('button');
      btn.className = 'nav-item' + (item.id === this.activeView ? ' active' : '');
      btn.dataset.view = item.id;
      btn.innerHTML = `${item.icon}<span>${item.label}</span>`;
      btn.addEventListener('click', () => this.handleClick(item.id));

      // Settings and Diagnostics go to system nav
      if (item.id === 'settings' || item.id === 'diagnostics') {
        systemNav.appendChild(btn);
      } else {
        navList.appendChild(btn);
      }
    });
  }

  private handleClick(view: string): void {
    this.setActive(view);
    this.onNavigate(view);
  }

  setActive(view: string): void {
    this.activeView = view;
    this.element.querySelectorAll('.nav-item').forEach((btn) => {
      btn.classList.toggle('active', (btn as HTMLElement).dataset.view === view);
    });
  }

  getElement(): HTMLElement {
    return this.element;
  }
}