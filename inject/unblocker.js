(function () {
  "use strict";

  const config = window.__UNBLOCKER_CONFIG__;
  if (!config) return;

  function fixUrl(urlStr) {
    try {
      if (!urlStr) return urlStr;
      if (urlStr.startsWith(config.prefix)) return urlStr;

      const base = new URL(config.url);
      const url = new URL(urlStr, base);

      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return urlStr;
      }

      return config.prefix + url.href;
    } catch {
      return urlStr;
    }
  }

  // =====================
  // fetch
  // =====================
  if (window.fetch) {
    const _fetch = window.fetch;
    window.fetch = function (resource, init) {
      if (resource && resource.url) {
        resource = new Request(fixUrl(resource.url), resource);
      } else {
        resource = fixUrl(resource.toString());
      }
      return _fetch(resource, init);
    };
  }

  // =====================
  // XMLHttpRequest
  // =====================
  if (window.XMLHttpRequest) {
    const XHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function () {
      const xhr = new XHR();
      const open = xhr.open;
      xhr.open = function (method, url) {
        return open.call(xhr, method, fixUrl(url));
      };
      return xhr;
    };
  }

  // =====================
  // createElement
  // =====================
  const _createElement = document.createElement.bind(document);
  document.createElement = function (tagName, options) {
    const el = _createElement(tagName, options);

    ["src", "href", "poster"].forEach(attr => {
      Object.defineProperty(el, attr, {
        set(value) {
          delete el[attr];
          el[attr] = fixUrl(value);
        },
        configurable: true
      });
    });

    return el;
  };

  // =====================
  // history API
  // =====================
  if (history.pushState) {
    const _push = history.pushState;
    history.pushState = function (state, title, url) {
      if (url) url = fixUrl(url);
      return _push.call(history, state, title, url);
    };
  }

  if (history.replaceState) {
    const _replace = history.replaceState;
    history.replaceState = function (state, title, url) {
      if (url) url = fixUrl(url);
      return _replace.call(history, state, title, url);
    };
  }

  // =====================
  // WebSocket
  // =====================
  if (window.WebSocket) {
    const WS = window.WebSocket;
    window.WebSocket = function (url, protocols) {
      if (typeof url === "string" && url.startsWith("ws")) {
        url = fixUrl(url.replace(/^ws/, "http")).replace(/^http/, "ws");
      }
      return new WS(url, protocols);
    };
  }

  // =====================
  // MutationObserver
  // =====================
  const observer = new MutationObserver(mutations => {
    for (const m of mutations) {
      if (m.type === "attributes") {
        const attr = m.attributeName;
        if (["src", "href", "poster"].includes(attr)) {
          const val = m.target.getAttribute(attr);
          const fixed = fixUrl(val);
          if (val !== fixed) {
            m.target.setAttribute(attr, fixed);
          }
        }
      }
    }
  });

  observer.observe(document.documentElement, {
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "href", "poster"]
  });

  console.log("[Web Unblocker] client initialized");
})();
