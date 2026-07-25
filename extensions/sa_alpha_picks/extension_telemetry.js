(function (root) {
  "use strict";

  var OUTBOX_STORAGE_KEY = "arkscope.sa.telemetryOutbox.v1";
  var OUTBOX_STATE_STORAGE_KEY = "arkscope.sa.telemetryOutboxState.v1";
  var LAST_RUN_STORAGE_KEY = "arkscope.sa.lastRun.v1";
  var DEFAULT_LIMITS = Object.freeze({
    maxRecords: 100,
    maxAgeMs: 7 * 24 * 60 * 60 * 1000,
    maxRecordBytes: 131072,
    maxTotalBytes: 4194304,
  });

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function canonicalize(value) {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (!isObject(value)) return value;
    var output = {};
    Object.keys(value).sort().forEach(function (key) {
      output[key] = canonicalize(value[key]);
    });
    return output;
  }

  function canonicalJson(value) {
    return JSON.stringify(canonicalize(value));
  }

  function utf8Bytes(value) {
    return new TextEncoder().encode(canonicalJson(value)).length;
  }

  function finitePositiveInteger(value, fallback) {
    return Number.isInteger(value) && value > 0 ? value : fallback;
  }

  function resolvedLimits(overrides) {
    overrides = overrides || {};
    return {
      maxRecords: finitePositiveInteger(overrides.maxRecords, DEFAULT_LIMITS.maxRecords),
      maxAgeMs: finitePositiveInteger(overrides.maxAgeMs, DEFAULT_LIMITS.maxAgeMs),
      maxRecordBytes: finitePositiveInteger(
        overrides.maxRecordBytes,
        DEFAULT_LIMITS.maxRecordBytes
      ),
      maxTotalBytes: finitePositiveInteger(
        overrides.maxTotalBytes,
        DEFAULT_LIMITS.maxTotalBytes
      ),
    };
  }

  function protocolProjection(result) {
    var candidate = {
      schema_version: result && result.schema_version,
      operation: result && result.operation,
      mode: result && result.mode,
      phases: result && result.phases,
      item_outcomes: result && result.item_outcomes,
    };
    if (result && result.counts !== undefined) candidate.counts = result.counts;
    if (result && result.derived_outcome !== undefined) {
      candidate.derived_outcome = result.derived_outcome;
    }
    if (result && result.healthy_anchor_eligible !== undefined) {
      candidate.healthy_anchor_eligible = result.healthy_anchor_eligible;
    }
    var derived = SAExtensionRunProtocol.deriveRunResult(candidate);
    return {
      schema_version: derived.schema_version,
      operation: derived.operation,
      mode: derived.mode,
      phases: derived.phases,
      item_outcomes: derived.item_outcomes,
      counts: derived.counts,
      derived_outcome: derived.derived_outcome,
      healthy_anchor_eligible: derived.healthy_anchor_eligible,
    };
  }

  function deliveryResult(record, delivery, reasonCode, runId) {
    return {
      client_event_id: record.client_event_id,
      delivery: delivery,
      reason_code: reasonCode || null,
      run_id: Number.isInteger(runId) ? runId : null,
    };
  }

  function immutableRecordValue(record) {
    return {
      client_event_id: record.client_event_id,
      started_at: record.started_at,
      finished_at: record.finished_at,
      result: record.result,
    };
  }

  function summaryFor(record, auditState, reasonCode, runId) {
    return {
      client_event_id: record.client_event_id,
      operation: record.result.operation,
      mode: record.result.mode,
      derived_outcome: record.result.derived_outcome,
      counts: record.result.counts,
      started_at: record.started_at,
      finished_at: record.finished_at,
      audit_state: auditState,
      audit_reason_code: reasonCode || null,
      run_id: Number.isInteger(runId) ? runId : null,
    };
  }

  function createController(options) {
    options = options || {};
    var storage = options.storage;
    var now = options.now || Date.now;
    var uuid = options.uuid;
    var deliver = options.deliver;
    var limits = resolvedLimits(options.limits);
    var flushPromise = null;

    if (!storage || typeof storage.get !== "function" || typeof storage.set !== "function") {
      throw new Error("telemetry storage adapter required");
    }
    if (typeof deliver !== "function") throw new Error("telemetry delivery adapter required");

    async function readState() {
      var values = await storage.get([
        OUTBOX_STORAGE_KEY,
        OUTBOX_STATE_STORAGE_KEY,
        LAST_RUN_STORAGE_KEY,
      ]);
      return {
        queue: Array.isArray(values[OUTBOX_STORAGE_KEY])
          ? values[OUTBOX_STORAGE_KEY]
          : [],
        state: isObject(values[OUTBOX_STATE_STORAGE_KEY])
          ? values[OUTBOX_STATE_STORAGE_KEY]
          : null,
        summary: isObject(values[LAST_RUN_STORAGE_KEY])
          ? values[LAST_RUN_STORAGE_KEY]
          : null,
      };
    }

    function evictionState(previous, count, reasonCode) {
      return {
        evicted_count: (previous && Number.isInteger(previous.evicted_count)
          ? previous.evicted_count
          : 0) + count,
        occurred_at: new Date(now()).toISOString(),
        reason_code: reasonCode,
      };
    }

    function applyQueueBounds(inputQueue, inputState) {
      var queue = inputQueue.slice();
      var state = inputState;
      var changed = false;
      var retainedBySize = queue.filter(function (candidate) {
        return utf8Bytes(candidate) <= limits.maxRecordBytes;
      });
      if (retainedBySize.length !== queue.length) {
        state = evictionState(
          state,
          queue.length - retainedBySize.length,
          "record_too_large"
        );
        queue = retainedBySize;
        changed = true;
      }
      var cutoff = now() - limits.maxAgeMs;
      var retainedByAge = queue.filter(function (candidate) {
        var created = Date.parse(candidate.created_at);
        return Number.isFinite(created) && created >= cutoff;
      });
      if (retainedByAge.length !== queue.length) {
        state = evictionState(
          state,
          queue.length - retainedByAge.length,
          "age_limit"
        );
        queue = retainedByAge;
        changed = true;
      }
      if (queue.length > limits.maxRecords) {
        var countOverflow = queue.length - limits.maxRecords;
        queue.splice(0, countOverflow);
        state = evictionState(state, countOverflow, "count_limit");
        changed = true;
      }
      var totalBytes = queue.reduce(function (sum, candidate) {
        return sum + utf8Bytes(candidate);
      }, 0);
      var byteEvictions = 0;
      while (queue.length && totalBytes > limits.maxTotalBytes) {
        totalBytes -= utf8Bytes(queue.shift());
        byteEvictions += 1;
      }
      if (byteEvictions) {
        state = evictionState(state, byteEvictions, "total_byte_limit");
        changed = true;
      }
      return {queue: queue, state: state, changed: changed};
    }

    async function persistQueue(queue, state, summary) {
      var values = {};
      values[OUTBOX_STORAGE_KEY] = queue;
      if (state) values[OUTBOX_STATE_STORAGE_KEY] = state;
      if (summary) values[LAST_RUN_STORAGE_KEY] = summary;
      await storage.set(values);
    }

    function makeRecord(event) {
      if (!isObject(event)) throw new Error("invalid extension event");
      var clientEventId = typeof event.client_event_id === "string"
        ? event.client_event_id.trim()
        : "";
      if (!clientEventId && typeof uuid === "function") clientEventId = String(uuid());
      if (!clientEventId || typeof event.started_at !== "string"
          || typeof event.finished_at !== "string") {
        throw new Error("invalid extension event");
      }
      return {
        client_event_id: clientEventId,
        started_at: event.started_at,
        finished_at: event.finished_at,
        result: protocolProjection(event.result),
        attempt_count: 0,
        delivery_code: "pending",
        created_at: new Date(now()).toISOString(),
      };
    }

    async function enqueue(event) {
      var record;
      try {
        record = makeRecord(event);
      } catch (_) {
        return {
          client_event_id: event && event.client_event_id ? event.client_event_id : null,
          delivery: "unavailable",
          reason_code: "invalid_extension_event",
          run_id: null,
        };
      }

      if (utf8Bytes(record) > limits.maxRecordBytes) {
        return deliveryResult(record, "unavailable", "record_too_large", null);
      }

      try {
        var current = await readState();
        var immutable = canonicalJson(immutableRecordValue(record));
        var existing = current.queue.find(function (candidate) {
          return candidate.client_event_id === record.client_event_id;
        });
        if (existing) {
          if (canonicalJson(immutableRecordValue(existing)) !== immutable) {
            return deliveryResult(record, "unavailable", "event_conflict", null);
          }
          return deliveryResult(existing, "pending", existing.delivery_code, null);
        }

        var queue = current.queue.slice();
        queue.push(record);
        var bounded = applyQueueBounds(queue, current.state);
        queue = bounded.queue;
        var state = bounded.state;

        var queued = queue.some(function (candidate) {
          return candidate.client_event_id === record.client_event_id;
        });
        var summary = summaryFor(
          record,
          queued ? "pending" : "unavailable",
          queued ? null : "total_byte_limit",
          null
        );
        await persistQueue(queue, state, summary);
        return deliveryResult(
          record,
          queued ? "pending" : "unavailable",
          queued ? null : "total_byte_limit",
          null
        );
      } catch (_) {
        return deliveryResult(record, "unavailable", "storage_unavailable", null);
      }
    }

    async function updateAfterAttempt(record, response, failureCode) {
      var current = await readState();
      var matching = current.queue.find(function (candidate) {
        return candidate.client_event_id === record.client_event_id;
      });
      if (!matching) return deliveryResult(record, "unavailable", "event_conflict", null);
      if (canonicalJson(immutableRecordValue(matching))
          !== canonicalJson(immutableRecordValue(record))) {
        return deliveryResult(record, "unavailable", "event_conflict", null);
      }

      var persisted = response && response.persisted === true
        && Number.isInteger(response.run_id);
      var reasonCode = failureCode
        || (response && typeof response.error_code === "string" ? response.error_code : null)
        || (persisted ? null : "sidecar_unavailable");
      var queue;
      var result;
      if (persisted) {
        queue = current.queue.filter(function (candidate) {
          return candidate.client_event_id !== record.client_event_id;
        });
        result = deliveryResult(record, "persisted", null, response.run_id);
      } else {
        queue = current.queue.map(function (candidate) {
          if (candidate.client_event_id !== record.client_event_id) return candidate;
          return Object.assign({}, candidate, {
            attempt_count: (Number.isInteger(candidate.attempt_count)
              ? candidate.attempt_count
              : 0) + 1,
            delivery_code: reasonCode,
          });
        });
        result = deliveryResult(record, "pending", reasonCode, null);
      }
      var summary = current.summary;
      if (!summary || summary.client_event_id === record.client_event_id) {
        summary = summaryFor(
          record,
          persisted ? "persisted" : "pending",
          reasonCode,
          persisted ? response.run_id : null
        );
      }
      await persistQueue(queue, current.state, summary);
      return result;
    }

    async function runFlush() {
      var current;
      try {
        current = await readState();
        var bounded = applyQueueBounds(current.queue, current.state);
        if (bounded.changed) {
          await persistQueue(bounded.queue, bounded.state, current.summary);
          current.queue = bounded.queue;
          current.state = bounded.state;
        }
      } catch (_) {
        return [];
      }
      var results = [];
      for (var index = 0; index < current.queue.length; index += 1) {
        var record = current.queue[index];
        var response = null;
        var failureCode = null;
        try {
          response = await deliver({
            client_event_id: record.client_event_id,
            started_at: record.started_at,
            finished_at: record.finished_at,
            result: record.result,
          });
        } catch (_) {
          failureCode = "sidecar_unavailable";
        }
        try {
          var result = await updateAfterAttempt(record, response, failureCode);
          results.push(result);
          if (result.delivery !== "persisted") break;
        } catch (_) {
          results.push(deliveryResult(record, "pending", "storage_unavailable", null));
          break;
        }
      }
      return results;
    }

    function flush(_trigger) {
      if (flushPromise) return flushPromise;
      flushPromise = runFlush().finally(function () {
        flushPromise = null;
      });
      return flushPromise;
    }

    async function submit(event) {
      var queued = await enqueue(event);
      if (queued.delivery === "unavailable") return queued;
      var results = await flush("submit");
      var matching = results.find(function (result) {
        return result.client_event_id === queued.client_event_id;
      });
      return matching || queued;
    }

    return Object.freeze({enqueue: enqueue, flush: flush, submit: submit});
  }

  root.SAExtensionTelemetry = Object.freeze({
    DEFAULT_LIMITS: DEFAULT_LIMITS,
    LAST_RUN_STORAGE_KEY: LAST_RUN_STORAGE_KEY,
    OUTBOX_STATE_STORAGE_KEY: OUTBOX_STATE_STORAGE_KEY,
    OUTBOX_STORAGE_KEY: OUTBOX_STORAGE_KEY,
    createController: createController,
  });
}(globalThis));
