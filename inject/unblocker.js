(function (global) {
  "use strict";

  const config = global.__UNBLOCKER_CONFIG__;
  if (!config || !config.prefix || !config.url) return;

  const PREFIX = config.prefix;

  // =====================
  // fixUrl (core)
  // =====================
  function fixUrl(urlStr) {
    try {
      if (!urlStr || typeof urlStr !== "string") return urlStr;

      // already proxied
      if (urlStr.startsWith(PREFIX)) return urlStr;

      // ignore special schemes
      if (
        urlStr.startsWith("data:") ||
        urlStr.startsWith("blob:") ||
        urlStr.startsWith("about:")
      ) {
        return urlStr;
      }

      const base = new URL(config.url);
      const url = new URL(urlStr, base);

      if (url.protocol !== "http:" && url.protocol !== "https:") {
        return urlStr;
      }

      return PREFIX + url.href;
    } catch (e) {
      return urlStr;
    }
  }

  // =====================
  // fetch
  // =====================
  if (global.fetch) {
    const _fetch = global.fetch;
    global.fetch = function (input, init) {
      try {
        if (typeof input === "string") {
          input = fixUrl(input);
        } else if (input instanceof Request) {
          input = new Request(fixUrl(input.url), input);
        }
      } catch (_) {}
      return _fetch.call(this, input, init);
    };
  }

  // =====================
  // XMLHttpRequest
  // =====================
  if (global.XMLHttpRequest) {
    const XHR = global.XMLHttpRequest;
    global.XMLHttpRequest = function () {
      const xhr = new XHR();
      const _open = xhr.open;
      xhr.open = function (method, url, async, user, password) {
        return _open.call(
          xhr,
          method,
          fixUrl(url),
          async !== undefined ? async : true,
          user,
          password
        );
      };
      return xhr;
    };
  }

  // =====================
  // document.createElement
  // =====================
  if (document.createElement) {
    const _createElement = document.createElement.bind(document);
    document.createElement = function (tagName, options) {
      const el = _createElement(tagName, options);

      ["src", "href", "poster"].forEach((attr) => {
        if (attr in el) {
          let internalValue = "";
          Object.defineProperty(el, attr, {
            get() {
              return internalValue;
            },
            set(value) {
              internalValue = fixUrl(value);
              el.setAttribute(attr, internalValue);
            },
            configurable: true,
          });
        }
      });

      return el;
    };
  }

  // =====================
  // history API
  // =====================
  function wrapHistory(fnName) {
    const original = history[fnName];
    if (!original) return;
    history[fnName] = function (state, title, url) {
      if (url) {
        url = fixUrl(url);
        try {
          config.url = new URL(url.replace(PREFIX, ""));
        } catch (_) {}
      }
      return original.call(history, state, title, url);
    };
  }

  wrapHistory("pushState");
  wrapHistory("replaceState");

  // =====================
  // WebSocket
  // =====================
  if (global.WebSocket) {
    const WS = global.WebSocket;
    global.WebSocket = function (url, protocols) {
      try {
        if (typeof url === "string" && /^wss?:\/\//.test(url)) {
          const httpUrl = url.replace(/^ws/, "http");
          const proxied = fixUrl(httpUrl);
          url = proxied.replace(/^http/, "ws");
        }
      } catch (_) {}
      return new WS(url, protocols);
    };
  }

  // =====================
  // MutationObserver
  // =====================
  const observer = new MutationObserver((mutations) => {
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
    attributeFilter: ["src", "href", "poster"],
  });

  console.log("[Web Unblocker] NodeUnblocker client initialized");
})(this);
