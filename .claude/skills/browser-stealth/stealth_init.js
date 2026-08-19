// Stealth initScript for chrome-devtools-mcp navigate_page
// Pass this as the `initScript` parameter on every navigate_page call
// Covers layers 1+2: navigator patches, fingerprint noise, plugin spoofing

// 1. navigator.webdriver — primary bot signal
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. window.chrome — missing in headless, detected by sites
if (!window.chrome) {
  window.chrome = {
    runtime: {
      sendMessage: function() {},
      connect: function() {
        return { onMessage: { addListener: () => {} }, postMessage: () => {} };
      }
    },
    loadTimes: function() { return {}; },
    csi: function() { return {}; },
    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } }
  };
}

// 3. navigator.plugins — empty in headless, should show standard plugins
Object.defineProperty(navigator, 'plugins', {
  get: () => {
    const makePlugin = (name, filename, desc) => {
      const p = Object.create(Plugin.prototype);
      Object.defineProperties(p, {
        name: { get: () => name },
        filename: { get: () => filename },
        description: { get: () => desc },
        length: { get: () => 1 }
      });
      return p;
    };
    const arr = [
      makePlugin('Chrome PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
      makePlugin('Chrome PDF Viewer', 'mhjfbmdgcfjbbpaeojofohoefgiehjai', ''),
      makePlugin('Native Client', 'internal-nacl-plugin', '')
    ];
    Object.setPrototypeOf(arr, PluginArray.prototype);
    Object.defineProperty(arr, 'length', { get: () => 3 });
    return arr;
  }
});

// 4. navigator.languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// 5. navigator.permissions — headless returns wrong state for notifications
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
  params.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : origQuery.call(window.navigator.permissions, params);

// 6. WebGL vendor/renderer spoofing
const getParam = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
  if (p === 37446) return 'Google Inc. (Intel)';
  if (p === 37445) return 'ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 655, OpenGL 4.1)';
  return getParam.call(this, p);
};
if (typeof WebGL2RenderingContext !== 'undefined') {
  const getParam2 = WebGL2RenderingContext.prototype.getParameter;
  WebGL2RenderingContext.prototype.getParameter = function(p) {
    if (p === 37446) return 'Google Inc. (Intel)';
    if (p === 37445) return 'ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 655, OpenGL 4.1)';
    return getParam2.call(this, p);
  };
}

// 7. Canvas fingerprint noise — subtle pixel randomization
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
  const ctx = this.getContext && this.getContext('2d');
  if (ctx && this.width > 0 && this.height > 0) {
    try {
      const img = ctx.getImageData(0, 0, Math.min(this.width, 32), Math.min(this.height, 32));
      for (let i = 0; i < img.data.length; i += 4) {
        img.data[i] = img.data[i] ^ (Math.random() > 0.5 ? 1 : 0);
      }
      ctx.putImageData(img, 0, 0);
    } catch(e) {}
  }
  return origToDataURL.apply(this, arguments);
};

// 8. AudioContext fingerprint noise
const ACtx = window.AudioContext || window.webkitAudioContext;
if (ACtx) {
  const origCreateOsc = ACtx.prototype.createOscillator;
  ACtx.prototype.createOscillator = function() {
    const osc = origCreateOsc.apply(this, arguments);
    const origConnect = osc.connect.bind(osc);
    osc.connect = function(dest) {
      if (dest instanceof AnalyserNode) {
        const origGetFloat = dest.getFloatFrequencyData.bind(dest);
        dest.getFloatFrequencyData = function(arr) {
          origGetFloat(arr);
          for (let i = 0; i < arr.length; i++) arr[i] += Math.random() * 0.0001;
        };
      }
      return origConnect(dest);
    };
    return osc;
  };
}

// 9. window.outerWidth/outerHeight — 0 in headless
if (window.outerWidth === 0) {
  Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
  Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
}

// 10. Notification.permission — default in headless vs real
if (Notification.permission === 'default') {
  Object.defineProperty(Notification, 'permission', { get: () => 'default' });
}

// 11. navigator.connection — missing in some headless modes
if (!navigator.connection) {
  Object.defineProperty(navigator, 'connection', {
    get: () => ({
      effectiveType: '4g',
      rtt: 50,
      downlink: 10,
      saveData: false
    })
  });
}
