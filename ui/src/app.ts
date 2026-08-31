// NEXORA — Core Application Controller

import { IPCClient } from './lib/ipc';
import { ThreeScene } from './scenes/ThreeScene';
import { Sidebar } from './components/Sidebar';
import { ChatOverlay } from './components/ChatOverlay';
import { RightPanel } from './components/RightPanel';
import { StatusBar } from './components/StatusBar';
import { SettingsModal } from './screens/SettingsModal';
import { DiagnosticsModal } from './screens/DiagnosticsModal';
import { VoiceController } from './components/VoiceController';
import { Terminal } from './components/Terminal';
import { FileExplorer } from './components/FileExplorer';
import { ConfirmationDialog } from './components/ConfirmationDialog';
import { CodingWorkspace } from './components/CodingWorkspace';
import { WebSearch } from './components/WebSearch';
import { SecurityPanel } from './components/SecurityPanel';
import { PluginManager } from './components/PluginManager';
import { Marketplace } from './components/Marketplace';

export class App {
  private ipc: IPCClient;
  private threeScene: ThreeScene | null = null;
  private sidebar: Sidebar | null = null;
  private chatOverlay: ChatOverlay | null = null;
  private rightPanel: RightPanel | null = null;
  private statusBar: StatusBar | null = null;
  private settingsModal: SettingsModal | null = null;
  private diagnosticsModal: DiagnosticsModal | null = null;
  private voiceController: VoiceController | null = null;
  private terminal: Terminal | null = null;
  private fileExplorer: FileExplorer | null = null;
  private confirmDialog: ConfirmationDialog | null = null;
  private codingWorkspace: CodingWorkspace | null = null;
  private webSearch: WebSearch | null = null;
  private securityPanel: SecurityPanel | null = null;
  private pluginManager: PluginManager | null = null;
  private marketplace: Marketplace | null = null;

  constructor() {
    this.ipc = new IPCClient();
  }

  async init(): Promise<void> {
    // Connect to backend
    await this.ipc.connect();

    // Ensure the .main grid area exists for ThreeScene and ChatOverlay
    const app = document.getElementById('app');
    if (app && !app.querySelector('.main')) {
      const main = document.createElement('div');
      main.className = 'main';
      app.appendChild(main);
    }

    // Initialize UI components
    this.threeScene = new ThreeScene(this.ipc);
    this.sidebar = new Sidebar(this.ipc, (view) => this.switchView(view));
    this.chatOverlay = new ChatOverlay(this.ipc);
    this.rightPanel = new RightPanel(this.ipc);
    this.statusBar = new StatusBar(this.ipc);
    this.settingsModal = new SettingsModal(this.ipc);
    this.diagnosticsModal = new DiagnosticsModal(this.ipc);
    this.voiceController = new VoiceController(this.ipc);
    void this.voiceController;
    this.terminal = new Terminal(this.ipc);
    this.fileExplorer = new FileExplorer(this.ipc);
    this.confirmDialog = new ConfirmationDialog(this.ipc);
    void this.confirmDialog;
    this.codingWorkspace = new CodingWorkspace(this.ipc);
    this.webSearch = new WebSearch(this.ipc);
    this.securityPanel = new SecurityPanel(this.ipc);
    this.pluginManager = new PluginManager(this.ipc);
    this.marketplace = new Marketplace(this.ipc);

    // Start Three.js scene
    this.threeScene.start();

    // Load initial data
    await this.refreshData();

    // Set up periodic updates
    setInterval(() => this.refreshData(), 5000);

    console.log('NEXORA UI initialized');
  }

  private async refreshData(): Promise<void> {
    try {
      await Promise.all([
        this.rightPanel?.refresh(),
        this.statusBar?.refresh(),
        this.chatOverlay?.loadConversations(),
      ]);
    } catch (e) {
      console.warn('Refresh failed:', e);
    }
  }

  switchView(view: string): void {
    this.sidebar?.setActive(view);

    // Show/hide components based on view
    const chatContainer = document.querySelector('.chat-overlay') as HTMLElement;
    if (chatContainer) {
      chatContainer.style.display = view === 'chat' ? 'block' : 'none';
    }

    // Hide all view-specific components
    this.terminal?.hide();
    this.fileExplorer?.hide();
    this.codingWorkspace?.hide();
    this.webSearch?.hide();
    this.securityPanel?.hide();
    this.pluginManager?.hide();
    this.marketplace?.hide();

    if (view === 'settings') {
      this.settingsModal?.open();
    } else if (view === 'diagnostics') {
      this.diagnosticsModal?.open();
    } else if (view === 'terminal') {
      this.terminal?.show();
    } else if (view === 'coding' || view === 'projects') {
      this.codingWorkspace?.show();
    } else if (view === 'browser') {
      this.webSearch?.show();
    } else if (view === 'security') {
      this.securityPanel?.show();
    } else if (view === 'plugins') {
      this.pluginManager?.show();
    } else if (view === 'marketplace') {
      this.marketplace?.show();
    } else if (view === 'chat') {
      this.fileExplorer?.show();
    }
  }

  async shutdown(): Promise<void> {
    this.threeScene?.dispose();
    await this.ipc.disconnect();
  }
}