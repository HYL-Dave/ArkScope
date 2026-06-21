"use strict";

function _origin(url) {
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

function shouldOpenExternal(targetUrl, currentUrl) {
  let target;
  try {
    target = new URL(targetUrl);
  } catch {
    return false;
  }
  if (target.protocol !== "http:" && target.protocol !== "https:") return false;
  const currentOrigin = _origin(currentUrl);
  return !currentOrigin || target.origin !== currentOrigin;
}

module.exports = { shouldOpenExternal };
