// Chat Overlay Component

import { IPCClient } from '../lib/ipc';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  provider?: string;
  model?: string;
  timestamp?: number;
}

export class ChatOverlay {
  private element: HTMLElement;
  private ipc: IPCClient;
  private messages: Message[] = [];
  private conversationId: string | null = null;
  private streaming = false;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
    this.setupListeners();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'chat-overlay';
    div.innerHTML = `
      <div class="chat-header">
        <span class="chat-title">NEXORA Chat</span>
        <div class="chat-status">
          <span class="status-dot"></span>
          <span class="status-text">Ready</span>
        </div>
      </div>
      <div class="chat-messages"></div>
      <div class="chat-input-area">
        <input type="text" class="chat-input" placeholder="Ask NEXORA..." autocomplete="off" />
        <button class="chat-send" disabled>Send</button>
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
    const input = this.element.querySelector('.chat-input') as HTMLInputElement;
    const sendBtn = this.element.querySelector('.chat-send') as HTMLButtonElement;

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && input.value.trim()) {
        e.preventDefault();
        this.sendMessage(input.value.trim());
      }
    });

    input.addEventListener('input', () => {
      sendBtn.disabled = !input.value.trim() || this.streaming;
    });

    sendBtn.addEventListener('click', () => {
      if (input.value.trim() && !this.streaming) {
        this.sendMessage(input.value.trim());
      }
    });

    // Listen for streaming chunks
    this.ipc.on('chat_chunk', (_evt: string, data: any) => this.handleChunk(data));
    this.ipc.on('chat_chunk_start', (_evt: string, data: any) => this.handleChunkStart(data));
    this.ipc.on('chat_chunk_end', () => this.handleChunkEnd());
    this.ipc.on('connected', () => this.updateStatus('connected', 'Connected'));
    this.ipc.on('disconnected', () => this.updateStatus('disconnected', 'Disconnected'));
  }

  private async sendMessage(text: string): Promise<void> {
    const input = this.element.querySelector('.chat-input') as HTMLInputElement;
    const sendBtn = this.element.querySelector('.chat-send') as HTMLButtonElement;

    input.value = '';
    sendBtn.disabled = true;
    this.streaming = true;
    this.updateStatus('working', 'Thinking...');

    // Add user message immediately
    this.addMessage({ role: 'user', content: text, timestamp: Date.now() });

    try {
      await this.ipc.chatStream(text, undefined, this.conversationId || undefined);
    } catch (e) {
      console.error('Chat error:', e);
      this.addMessage({
        role: 'assistant',
        content: `Error: ${(e as Error).message}`,
        timestamp: Date.now(),
      });
      this.streaming = false;
      this.updateStatus('error', 'Error');
      sendBtn.disabled = false;
    }
  }

  private handleChunkStart(data: any): void {
    this.conversationId = data.conversation_id;
    // Create placeholder for assistant message
    this.messages.push({ role: 'assistant', content: '', timestamp: Date.now() });
    this.renderMessages();
  }

  private handleChunk(data: any): void {
    // Update last message (assistant)
    const lastIdx = this.messages.length - 1;
    if (lastIdx >= 0 && this.messages[lastIdx].role === 'assistant') {
      this.messages[lastIdx].content += data.content;
      this.renderMessages();
    }
  }

  private handleChunkEnd(): void {
    this.streaming = false;
    const sendBtn = this.element.querySelector('.chat-send') as HTMLButtonElement;
    sendBtn.disabled = false;
    this.updateStatus('connected', 'Ready');
  }

  private addMessage(msg: Message): void {
    this.messages.push(msg);
    this.renderMessages();
  }

  private renderMessages(): void {
    const container = this.element.querySelector('.chat-messages') as HTMLElement;
    if (!container) return;

    container.innerHTML = this.messages.map((msg) => `
      <div class="chat-message ${msg.role}">
        <div class="avatar">${msg.role === 'user' ? 'U' : 'N'}</div>
        <div class="content">
          <div>${this.escapeHtml(msg.content)}</div>
          <div class="meta">${msg.provider || ''} ${msg.model ? `• ${msg.model}` : ''} • ${new Date(msg.timestamp || Date.now()).toLocaleTimeString()}</div>
        </div>
      </div>
    `).join('');

    container.scrollTop = container.scrollHeight;
  }

  private updateStatus(state: string, text: string): void {
    const dot = this.element.querySelector('.status-dot') as HTMLElement;
    const statusText = this.element.querySelector('.status-text') as HTMLElement;
    if (dot) dot.className = `status-dot ${state}`;
    if (statusText) statusText.textContent = text;
  }

  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  async loadConversations(): Promise<void> {
    try {
      await this.ipc.listConversations();
      // Could show in a dropdown
    } catch (e) {
      console.warn('Failed to load conversations:', e);
    }
  }
}