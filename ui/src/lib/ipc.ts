// IPC Client — WebSocket connection to backend

type MessageHandler = (event: string, data: any) => void;

export class IPCClient {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private pending: Map<string, { resolve: (v: any) => void; reject: (e: Error) => void }> = new Map();
  private requestId = 0;
  private reconnectTimer: number | null = null;
  private connected = false;

  constructor() {
    // Backend serves both API and UI on same port
    this.url = `ws://${window.location.host}/ws`;
  }

  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
          this.connected = true;
          this.emit('connected', {});
          resolve();
        };

        this.ws.onmessage = (event) => this.handleMessage(event.data);
        this.ws.onclose = () => this.handleClose();
        this.ws.onerror = () => {
          if (!this.connected) {
            reject(new Error('Failed to connect to backend'));
          }
        };
      } catch (e) {
        reject(e);
      }
    });
  }

  private handleMessage(data: string | ArrayBuffer): void {
    try {
      const msg = JSON.parse(data.toString());

      if (msg.type === 'response') {
        const pending = this.pending.get(msg.id);
        if (pending) {
          this.pending.delete(msg.id);
          if (msg.code) {
            pending.reject(new Error(msg.message));
          } else {
            pending.resolve(msg.result);
          }
        }
      } else if (msg.type === 'error') {
        const pending = this.pending.get(msg.id);
        if (pending) {
          this.pending.delete(msg.id);
          pending.reject(new Error(`${msg.code}: ${msg.message}`));
        }
      } else if (msg.type === 'event') {
        this.emit(msg.event, msg.data);
      }
    } catch {
      console.warn('Failed to parse IPC message');
    }
  }

  private handleClose(): void {
    this.connected = false;
    this.emit('disconnected', {});

    // Reject pending requests
    for (const [, p] of this.pending) {
      p.reject(new Error('Connection closed'));
    }
    this.pending.clear();

    // Attempt reconnection
    if (!this.reconnectTimer) {
      this.reconnectTimer = window.setTimeout(() => {
        this.reconnectTimer = null;
        this.connect().catch(() => {});
      }, 2000);
    }
  }

  private emit(event: string, data: any): void {
    const handlers = this.handlers.get(event) || [];
    for (const h of handlers) {
      try {
        h(event, data);
      } catch (e) {
        console.error(`Handler error for ${event}:`, e);
      }
    }
  }

  on(event: string, handler: MessageHandler): () => void {
    const list = this.handlers.get(event) || [];
    list.push(handler);
    this.handlers.set(event, list);
    return () => this.off(event, handler);
  }

  off(event: string, handler: MessageHandler): void {
    const list = this.handlers.get(event) || [];
    const idx = list.indexOf(handler);
    if (idx >= 0) list.splice(idx, 1);
  }

  async request(method: string, params: any = {}): Promise<any> {
    if (!this.connected || !this.ws) {
      throw new Error('Not connected');
    }

    const id = String(++this.requestId);
    const msg = { id, method, params };

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws!.send(JSON.stringify(msg));

      // Timeout
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error('Request timeout'));
        }
      }, 30000);
    });
  }

  async disconnect(): Promise<void> {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  // Convenience methods
  async ping(): Promise<any> {
    return this.request('ping');
  }

  async chat(message: string, providerId?: string, conversationId?: string): Promise<any> {
    return this.request('chat', { message, provider_id: providerId, conversation_id: conversationId });
  }

  async chatStream(message: string, providerId?: string, conversationId?: string): Promise<any> {
    return this.request('chat_stream', { message, provider_id: providerId, conversation_id: conversationId });
  }

  async listProviders(): Promise<any> {
    return this.request('providers.list');
  }

  async addProvider(type: string, name: string, model: string, apiKey?: string, baseUrl?: string, extra?: any): Promise<any> {
    return this.request('providers.add', { type, name, model, api_key: apiKey, base_url: baseUrl, extra });
  }

  async removeProvider(id: string): Promise<any> {
    return this.request('providers.remove', { id });
  }

  async testProvider(id: string): Promise<any> {
    return this.request('providers.test', { id });
  }

  async runDiagnostics(): Promise<any> {
    return this.request('diagnostics');
  }

  async listConversations(): Promise<any> {
    return this.request('conversations.list');
  }

  async createConversation(title: string, providerId?: string, model?: string): Promise<any> {
    return this.request('conversations.create', { title, provider_id: providerId, model });
  }

  async getConversation(id: string): Promise<any> {
    return this.request('conversations.get', { conversation_id: id });
  }

  async getSettings(): Promise<any> {
    return this.request('settings.get');
  }

  async setSetting(key: string, value: any): Promise<any> {
    return this.request('settings.set', { key, value });
  }

  async shutdown(): Promise<any> {
    return this.request('shutdown');
  }

  // Voice methods
  async getVoiceState(): Promise<any> {
    return this.request('voice.state');
  }

  async voiceListen(duration?: number): Promise<any> {
    return this.request('voice.listen', { duration: duration || 5 });
  }

  async voiceSpeak(text: string): Promise<any> {
    return this.request('voice.speak', { text });
  }

  async voiceStop(): Promise<any> {
    return this.request('voice.stop');
  }

  async getVoiceDevices(): Promise<any> {
    return this.request('voice.devices');
  }

  async configureVoice(config: any): Promise<any> {
    return this.request('voice.configure', config);
  }
}