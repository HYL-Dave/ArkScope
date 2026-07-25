import fs from "node:fs";
import vm from "node:vm";

const [protocolPath, telemetryPath, fixturePath, scenario] = process.argv.slice(2);
const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function createStorage(initial = {}, options = {}) {
  const data = clone(initial);
  const writes = [];
  return {
    data,
    writes,
    async get(keys) {
      const names = Array.isArray(keys) ? keys : [keys];
      return Object.fromEntries(names.map((key) => [key, clone(data[key])]));
    },
    async set(values) {
      writes.push(clone(values));
      if (options.failSet) throw new Error("synthetic storage failure");
      Object.assign(data, clone(values));
    },
  };
}

const context = vm.createContext({console, TextEncoder, setTimeout, clearTimeout});
vm.runInContext(fs.readFileSync(protocolPath, "utf8"), context, {filename: protocolPath});
vm.runInContext(fs.readFileSync(telemetryPath, "utf8"), context, {filename: telemetryPath});
const telemetry = context.SAExtensionTelemetry;

function protocolInput(name) {
  return clone(fixture.protocol_cases.find((entry) => entry.name === name).input);
}

function event(id, name = "complete_market_sync", offsetMs = 0) {
  const started = new Date(Date.UTC(2026, 6, 25, 1, 0, 0) + offsetMs);
  return {
    client_event_id: id,
    started_at: started.toISOString(),
    finished_at: new Date(started.getTime() + 30000).toISOString(),
    result: protocolInput(name),
  };
}

async function run() {
  const outboxKey = telemetry.OUTBOX_STORAGE_KEY;
  const stateKey = telemetry.OUTBOX_STATE_STORAGE_KEY;

  if (scenario === "commit_before_delivery") {
    const order = [];
    const storage = createStorage();
    const originalSet = storage.set;
    storage.set = async (values) => {
      order.push("set");
      return originalSet.call(storage, values);
    };
    let queueLengthAtDelivery = null;
    const controller = telemetry.createController({
      storage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "generated-commit",
      deliver: async () => {
        order.push("deliver");
        queueLengthAtDelivery = (storage.data[outboxKey] || []).length;
        return {persisted: true, run_id: 41};
      },
    });
    const result = await controller.submit(event("evt-commit"));
    return {order, queueLengthAtDelivery, result, queue: storage.data[outboxKey]};
  }

  if (scenario === "remove_matching_only") {
    const storage = createStorage();
    const controller = telemetry.createController({
      storage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async (record) => record.client_event_id === "evt-first"
        ? {persisted: true, run_id: 42}
        : {persisted: false, error_code: "sidecar_unavailable"},
    });
    await controller.enqueue(event("evt-first"));
    await controller.enqueue(event("evt-second", "top_level_ok_with_retryable_details", 1000));
    await controller.flush("test");
    return {queue: storage.data[outboxKey], summary: storage.data[telemetry.LAST_RUN_STORAGE_KEY]};
  }

  if (scenario === "sidecar_unavailable") {
    const storage = createStorage();
    const controller = telemetry.createController({
      storage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => { throw new Error("synthetic sidecar outage"); },
    });
    const result = await controller.submit(event("evt-pending"));
    return {result, queue: storage.data[outboxKey], summary: storage.data[telemetry.LAST_RUN_STORAGE_KEY]};
  }

  if (scenario === "duplicate_retry") {
    const storage = createStorage();
    const ids = [];
    let attempts = 0;
    const controller = telemetry.createController({
      storage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async (record) => {
        ids.push(record.client_event_id);
        attempts += 1;
        return attempts === 1
          ? {persisted: false, error_code: "sidecar_unavailable"}
          : {persisted: true, run_id: 43};
      },
    });
    await controller.enqueue(event("evt-duplicate"));
    await controller.flush("first");
    await controller.flush("retry");
    return {ids, queue: storage.data[outboxKey]};
  }

  if (scenario === "serialized_flush") {
    const storage = createStorage();
    let deliveries = 0;
    const controller = telemetry.createController({
      storage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => {
        deliveries += 1;
        await new Promise((resolve) => setTimeout(resolve, 15));
        return {persisted: true, run_id: 44};
      },
    });
    await controller.enqueue(event("evt-serialized"));
    await Promise.all([
      controller.flush("startup"),
      controller.flush("popup_open"),
      controller.flush("next_job"),
    ]);
    return {deliveries, queue: storage.data[outboxKey]};
  }

  if (scenario === "count_and_bytes") {
    const countStorage = createStorage();
    const countController = telemetry.createController({
      storage: countStorage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => ({persisted: false}),
      limits: {maxRecords: 2},
    });
    await countController.enqueue(event("evt-count-1", "complete_market_sync", 1));
    await countController.enqueue(event("evt-count-2", "complete_market_sync", 2));
    await countController.enqueue(event("evt-count-3", "complete_market_sync", 3));

    const byteStorage = createStorage();
    const byteController = telemetry.createController({
      storage: byteStorage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => ({persisted: false}),
      limits: {maxTotalBytes: 1},
    });
    await byteController.enqueue(event("evt-byte"));
    return {
      countQueue: countStorage.data[outboxKey],
      countState: countStorage.data[stateKey],
      byteQueue: byteStorage.data[outboxKey],
      byteState: byteStorage.data[stateKey],
    };
  }

  if (scenario === "age_bound") {
    let now = Date.UTC(2026, 6, 25, 2);
    const storage = createStorage();
    const controller = telemetry.createController({
      storage,
      now: () => now,
      uuid: () => "unused",
      deliver: async () => ({persisted: false}),
      limits: {maxAgeMs: 1000},
    });
    await controller.enqueue(event("evt-old"));
    now += 2000;
    await controller.enqueue(event("evt-current", "complete_market_sync", 2000));
    return {queue: storage.data[outboxKey], state: storage.data[stateKey]};
  }

  if (scenario === "unavailable_cases") {
    const oversizeStorage = createStorage();
    const oversizeController = telemetry.createController({
      storage: oversizeStorage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => ({persisted: true, run_id: 1}),
      limits: {maxRecordBytes: 1},
    });
    const oversize = await oversizeController.submit(event("evt-oversize"));

    const failedStorage = createStorage({}, {failSet: true});
    const failedController = telemetry.createController({
      storage: failedStorage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => ({persisted: true, run_id: 2}),
    });
    const storageFailure = await failedController.submit(event("evt-storage"));

    const conflictStorage = createStorage();
    const conflictController = telemetry.createController({
      storage: conflictStorage,
      now: () => Date.UTC(2026, 6, 25, 2),
      uuid: () => "unused",
      deliver: async () => ({persisted: false}),
    });
    await conflictController.enqueue(event("evt-conflict"));
    const conflict = await conflictController.enqueue(
      event("evt-conflict", "top_level_ok_with_retryable_details", 1000)
    );
    return {
      oversize,
      oversizeQueue: oversizeStorage.data[outboxKey] || [],
      storageFailure,
      storageQueue: failedStorage.data[outboxKey] || [],
      conflict,
      conflictQueue: conflictStorage.data[outboxKey],
    };
  }

  throw new Error(`unknown scenario: ${scenario}`);
}

process.stdout.write(JSON.stringify(await run()));
