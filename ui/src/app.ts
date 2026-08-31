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
    // VoiceController self-mounts into the chat header — keep reference alive
    void this.voiceController;

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

    // Handle special views
    if (view === 'settings') {
      this.settingsModal?.open();
    } else if (view === 'diagnostics') {
      this.diagnosticsModal?.open();
    }
  }

  async shutdown(): Promise<void> {
    this.threeScene?.dispose();
    await this.ipc.disconnect();
  }
}