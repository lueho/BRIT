(function () {
  const URL_SELECTOR = "a.js-compact-url";
  const MAX_SEGMENT_LENGTH = 28;

  function truncateMiddle(value, maxLength) {
    if (!value || value.length <= maxLength) {
      return value;
    }

    const keep = Math.floor((maxLength - 1) / 2);
    return `${value.slice(0, keep)}…${value.slice(value.length - keep)}`;
  }

  function normalizeHost(host) {
    if (!host) {
      return "";
    }
    return host.replace(/^www\./i, "");
  }

  function compactPath(pathname) {
    if (!pathname || pathname === "/") {
      return "";
    }

    const segments = pathname.split("/").filter(Boolean);
    if (!segments.length) {
      return "";
    }

    if (segments.length === 1) {
      return `/${truncateMiddle(segments[0], MAX_SEGMENT_LENGTH)}`;
    }

    const first = truncateMiddle(segments[0], 16);
    const last = truncateMiddle(segments[segments.length - 1], MAX_SEGMENT_LENGTH);
    return `/${first}/…/${last}`;
  }

  function parseWaybackUrl(urlString) {
    const waybackMatch = urlString.match(
      /^https?:\/\/web\.archive\.org\/web\/(\d{8,14})\/(https?:\/\/.+)$/i,
    );

    if (!waybackMatch) {
      return null;
    }

    const timestamp = waybackMatch[1];
    const originalUrl = waybackMatch[2];

    try {
      const parsedOriginalUrl = new URL(originalUrl);
      const host = normalizeHost(parsedOriginalUrl.hostname);
      const path = compactPath(parsedOriginalUrl.pathname);
      const date = `${timestamp.slice(0, 4)}-${timestamp.slice(4, 6)}-${timestamp.slice(6, 8)}`;
      return `Archive ${date} · ${host}${path}`;
    } catch (error) {
      return `Archive · ${truncateMiddle(originalUrl, 64)}`;
    }
  }

  function compactUrl(urlString) {
    const waybackLabel = parseWaybackUrl(urlString);
    if (waybackLabel) {
      return waybackLabel;
    }

    try {
      const parsedUrl = new URL(urlString);
      const host = normalizeHost(parsedUrl.hostname);
      const path = compactPath(parsedUrl.pathname);
      return `${host}${path}`;
    } catch (error) {
      return truncateMiddle(urlString, 72);
    }
  }

  function setCompactLabel(anchor) {
    const href = anchor.getAttribute("href");
    if (!href) {
      return;
    }

    const label = compactUrl(href);
    const labelContainer = anchor.querySelector(".source-url-label");

    if (labelContainer) {
      labelContainer.textContent = label;
    } else {
      anchor.textContent = label;
    }

    anchor.setAttribute("title", href);
    anchor.setAttribute("aria-label", `Open source link: ${href}`);
  }

  function initCompactUrls() {
    const links = document.querySelectorAll(URL_SELECTOR);
    links.forEach(setCompactLabel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCompactUrls);
  } else {
    initCompactUrls();
  }
})();
