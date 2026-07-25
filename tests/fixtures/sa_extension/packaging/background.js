importScripts("shared.js");

chrome.scripting.executeScript({
  target: {tabId: 1},
  files: ["article_identity.js", "scrape_list.js"],
});

chrome.scripting.executeScript({
  target: {tabId: 1},
  files: ["article_identity.js", "scrape_detail.js"],
});
