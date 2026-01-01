(function (global) {
  "use strict";

  const config = global.__UNBLOCKER_CONFIG__;
  if (!config || !config.prefix || !config.originUrl) return;

  const PREFIX = config.prefix;
  const ORIGIN = config.originUrl;

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

      const base = new URL(ORIGIN);
      const url = new URL(urlStr, base);

      if (!["http:", "https:"].includes(url.protocol)) {
        return urlStr;
      }

      return PREFIX + encodeURIComponent(url.href);
    } catch (_) {
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
        if (!(attr in el)) return;

        const desc = Object.getOwnPropertyDescriptor(
          Object.getPrototypeOf(el),
          attr
        );
        if (!desc || !desc.set) return;

        Object.defineProperty(el, attr, {
          get: desc.get ? desc.get.bind(el) : undefined,
          set(value) {
            desc.set.call(el, fixUrl(value));
          },
          configurable: true,
        });
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
        const fixed = fixUrl(url);
        try {
          const decoded = decodeURIComponent(
            fixed.startsWith(PREFIX)
              ? fixed.slice(PREFIX.length)
              : fixed
          );
          config.originUrl = decoded;
        } catch (_) {}
        return original.call(history, state, title, fixed);
      }
      return original.call(history, state, title);
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
      if (m.type !== "attributes") continue;

      const attr = m.attributeName;
      if (!["src", "href", "poster"].includes(attr)) continue;

      const el = m.target;
      const val = el.getAttribute(attr);
      if (!val || val.startsWith(PREFIX)) continue;

      const fixed = fixUrl(val);
      if (fixed !== val) {
        el.setAttribute(attr, fixed);
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
