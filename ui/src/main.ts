// NEXORA — Main entry point

import './styles/main.css';
import { App } from './app';

declare global {
  interface Window {
    NEXORA: App;
  }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
  window.NEXORA = app;
});