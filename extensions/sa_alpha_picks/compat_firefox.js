// Firefox-only compatibility shim.
//
// The Chrome build uses chrome.* directly and is untouched. Firefox supports
// chrome.* callbacks and browser.* promises; background.js expects promise
// returns for many chrome.* calls while popup.js still uses callbacks. This
// shim creates a chrome facade backed by browser.* promises and preserves
// callback-style lastError behavior for popup.js.
(function () {
  "use strict";

  if (typeof browser === "undefined") {
    return;
  }

  var nativeChrome = typeof chrome !== "undefined" ? chrome : {};
  var lastErrorValue;

  function isEventLike(value) {
    return !!value
      && typeof value === "object"
      && typeof value.addListener === "function"
      && typeof value.removeListener === "function";
  }

  function setLastError(error) {
    if (!error) {
      lastErrorValue = undefined;
      return;
    }
    lastErrorValue = {
      message: error && error.message ? error.message : String(error),
    };
    setTimeout(function () {
      lastErrorValue = undefined;
    }, 0);
  }

  function wrapFunction(fn, thisArg) {
    return function () {
      var args = Array.prototype.slice.call(arguments);
      var maybeCallback = args.length ? args[args.length - 1] : null;
      var callback = typeof maybeCallback === "function" ? args.pop() : null;
      var promise;

      try {
        promise = fn.apply(thisArg, args);
      } catch (error) {
        if (callback) {
          setLastError(error);
          callback();
          return undefined;
        }
        return Promise.reject(error);
      }

      if (!promise || typeof promise.then !== "function") {
        if (callback) {
          setLastError(undefined);
          callback(promise);
          return undefined;
        }
        return promise;
      }

      if (!callback) {
        return promise;
      }

      promise.then(function (result) {
        setLastError(undefined);
        callback(result);
      }, function (error) {
        setLastError(error);
        callback();
      });
      return undefined;
    };
  }

  function wrapObject(promiseObject, callbackObject) {
    if (!promiseObject || typeof promiseObject !== "object") {
      return promiseObject;
    }

    if (isEventLike(callbackObject)) {
      return callbackObject;
    }
    if (isEventLike(promiseObject)) {
      return promiseObject;
    }

    var keys = [];
    [promiseObject, callbackObject].forEach(function (source) {
      if (!source || typeof source !== "object") return;
      Object.getOwnPropertyNames(source).forEach(function (key) {
        if (keys.indexOf(key) === -1) keys.push(key);
      });
    });

    var output = {};
    keys.forEach(function (key) {
      var promiseValue = promiseObject[key];
      var callbackValue = callbackObject && callbackObject[key];

      if (isEventLike(callbackValue)) {
        output[key] = callbackValue;
      } else if (isEventLike(promiseValue)) {
        output[key] = promiseValue;
      } else if (typeof promiseValue === "function") {
        output[key] = wrapFunction(promiseValue, promiseObject);
      } else if (promiseValue && typeof promiseValue === "object") {
        output[key] = wrapObject(promiseValue, callbackValue);
      } else {
        output[key] = promiseValue;
      }
    });

    return output;
  }

  var chromeCompat = wrapObject(browser, nativeChrome);
  if (!chromeCompat.runtime) {
    chromeCompat.runtime = {};
  }
  Object.defineProperty(chromeCompat.runtime, "lastError", {
    configurable: true,
    enumerable: true,
    get: function () {
      return lastErrorValue;
    },
  });

  Object.defineProperty(globalThis, "chrome", {
    configurable: true,
    writable: true,
    value: chromeCompat,
  });
}());
