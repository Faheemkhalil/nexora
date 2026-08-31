// CodeEditor Component — file viewer with syntax highlighting and line numbers

import { IPCClient } from '../lib/ipc';

interface EditorFile {
  path: string;
  content: string;
  totalLines: number;
  language: string;
}

const LANG_MAP: Record<string, string> = {
  '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
  '.jsx': 'javascript', '.rs': 'rust', '.go': 'go', '.java': 'java',
  '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp',
  '.html': 'html', '.css': 'css', '.scss': 'scss', '.json': 'json',
  '.md': 'markdown', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
  '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
  '.sql': 'sql', '.xml': 'xml', '.svg': 'xml',
  '.txt': 'text', '.log': 'text', '.csv': 'text',
};

// Simple syntax highlighting
function highlightCode(code: string, language: string): string {
  if (language === 'text') return escapeHtml(code);

  const lines = code.split('\n');
  return lines.map(line => highlightLine(line, language)).join('\n');
}

function highlightLine(line: string, language: string): string {
  let result = escapeHtml(line);

  // Comments
  if (['python', 'bash', 'yaml'].includes(language)) {
    result = result.replace(/(#.*)$/gm, '<span class="hl-comment">$1</span>');
  }
  if (['javascript', 'typescript', 'c', 'cpp', 'java', 'go', 'rust', 'scss'].includes(language)) {
    result = result.replace(/(\/\/.*)$/gm, '<span class="hl-comment">$1</span>');
    result = result.replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="hl-comment">$1</span>');
  }

  // Strings (double and single quoted)
  result = result.replace(/(&quot;[^&]*?&quot;)/g, '<span class="hl-string">$1</span>');
  result = result.replace(/(&#x27;[^&]*?&#x27;)/g, '<span class="hl-string">$1</span>');
  result = result.replace(/(`[^`]*?`)/g, '<span class="hl-string">$1</span>');

  // Keywords
  const keywords = getKeywords(language);
  if (keywords) {
    const kwRegex = new RegExp(`\\b(${keywords.join('|')})\\b`, 'g');
    result = result.replace(kwRegex, '<span class="hl-keyword">$1</span>');
  }

  // Numbers
  result = result.replace(/\b(\d+\.?\d*)\b/g, '<span class="hl-number">$1</span>');

  // Functions
  result = result.replace(/\b([a-zA-Z_]\w*)\s*\(/g, '<span class="hl-function">$1</span>(');

  return result;
}

function getKeywords(language: string): string[] | null {
  const kw: Record<string, string[]> = {
    python: ['def', 'class', 'import', 'from', 'return', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'yield', 'async', 'await', 'pass', 'break', 'continue', 'raise', 'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'global', 'nonlocal', 'del', 'assert'],
    javascript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch', 'finally', 'throw', 'new', 'this', 'class', 'extends', 'import', 'export', 'default', 'from', 'async', 'await', 'yield', 'true', 'false', 'null', 'undefined', 'typeof', 'instanceof', 'in', 'of'],
    typescript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch', 'finally', 'throw', 'new', 'this', 'class', 'extends', 'import', 'export', 'default', 'from', 'async', 'await', 'yield', 'true', 'false', 'null', 'undefined', 'typeof', 'instanceof', 'interface', 'type', 'enum', 'implements', 'abstract', 'readonly', 'private', 'public', 'protected', 'static', 'override', 'keyof', 'infer', 'never', 'unknown', 'any', 'void', 'string', 'number', 'boolean'],
    rust: ['fn', 'let', 'mut', 'const', 'struct', 'enum', 'impl', 'trait', 'pub', 'use', 'mod', 'crate', 'self', 'super', 'if', 'else', 'for', 'while', 'loop', 'match', 'return', 'break', 'continue', 'async', 'await', 'move', 'ref', 'where', 'true', 'false', 'self', 'Self'],
    go: ['func', 'package', 'import', 'return', 'if', 'else', 'for', 'range', 'switch', 'case', 'default', 'break', 'continue', 'go', 'defer', 'select', 'chan', 'map', 'struct', 'interface', 'type', 'const', 'var', 'true', 'false', 'nil', 'make', 'new', 'len', 'cap', 'append'],
    c: ['int', 'float', 'double', 'char', 'void', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'return', 'struct', 'enum', 'typedef', 'const', 'static', 'extern', 'sizeof', 'NULL', 'true', 'false', 'include', 'define'],
    java: ['public', 'private', 'protected', 'static', 'final', 'abstract', 'class', 'interface', 'extends', 'implements', 'new', 'this', 'super', 'return', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch', 'finally', 'throw', 'throws', 'import', 'package', 'void', 'int', 'float', 'double', 'boolean', 'char', 'String', 'true', 'false', 'null'],
  };
  return kw[language] || null;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

function detectLanguage(filePath: string): string {
  const ext = '.' + filePath.split('.').pop()?.toLowerCase();
  return LANG_MAP[ext] || 'text';
}

export class CodeEditor {
  private element: HTMLElement;
  private ipc: IPCClient;
  private currentFile: EditorFile | null = null;

  constructor(ipc: IPCClient) {
    this.ipc = ipc;
    this.element = this.createElement();
    this.mount();
  }

  private createElement(): HTMLElement {
    const div = document.createElement('div');
    div.className = 'code-editor';
    div.style.display = 'none';
    div.innerHTML = `
      <div class="editor-header">
        <div class="editor-tabs">
          <span class="editor-tab active">
            <span class="editor-tab-name">No file open</span>
            <button class="editor-tab-close" title="Close file">×</button>
          </span>
        </div>
        <div class="editor-actions">
          <button class="editor-action" id="editor-save" title="Save (Ctrl+S)">💾</button>
          <button class="editor-action" id="editor-search" title="Search">🔍</button>
          <button class="editor-action" id="editor-close" title="Close editor">✕</button>
        </div>
      </div>
      <div class="editor-toolbar">
        <span class="editor-file-path">—</span>
        <span class="editor-lang">—</span>
        <span class="editor-lines">— lines</span>
      </div>
      <div class="editor-content">
        <div class="editor-line-numbers"></div>
        <pre class="editor-code"><code></code></pre>
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

  async openFile(path: string): Promise<void> {
    try {
      const result = await this.ipc.request('coding.read_file', { path, limit: 3000 });
      if (!result.success) {
        console.warn('Failed to read file:', result.error);
        return;
      }

      const language = detectLanguage(path);
      this.currentFile = {
        path,
        content: result.content,
        totalLines: result.total_lines,
        language,
      };

      this.render();
      this.show();
    } catch (e) {
      console.warn('File open failed:', e);
    }
  }

  private render(): void {
    if (!this.currentFile) return;

    const { content, totalLines, language, path } = this.currentFile;

    // Update header
    const tabName = this.element.querySelector('.editor-tab-name');
    if (tabName) tabName.textContent = path.split('/').pop() || path;

    const filePath = this.element.querySelector('.editor-file-path');
    if (filePath) filePath.textContent = path;

    const langEl = this.element.querySelector('.editor-lang');
    if (langEl) langEl.textContent = language;

    const linesEl = this.element.querySelector('.editor-lines');
    if (linesEl) linesEl.textContent = `${totalLines} lines`;

    // Render line numbers
    const lineNums = this.element.querySelector('.editor-line-numbers');
    if (lineNums) {
      lineNums.innerHTML = Array.from(
        { length: Math.min(totalLines, 3000) },
        (_, i) => `<div class="line-num">${i + 1}</div>`
      ).join('');
    }

    // Render highlighted code
    const codeEl = this.element.querySelector('.editor-code code');
    if (codeEl) {
      codeEl.innerHTML = highlightCode(content, language);
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

  isOpen(): boolean {
    return this.element.style.display !== 'none' && this.currentFile !== null;
  }

  getCurrentFile(): string | null {
    return this.currentFile?.path || null;
  }
}
