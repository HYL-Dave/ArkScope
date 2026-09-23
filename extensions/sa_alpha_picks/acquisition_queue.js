(function (root) {
  "use strict";

  function create(options) {
    var now = options && options.now || Date.now;
    var lanes = {routine: [], background: []};
    var jobs = new Map();
    var active = null;
    var pumping = false;

    async function pump() {
      if (pumping) return;
      pumping = true;
      try {
        while (lanes.routine.length || lanes.background.length) {
          var entry = lanes.routine.shift() || lanes.background.shift();
          try {
            if (entry.eligible && !await entry.eligible()) {
              entry.resolve({status:"skipped",reason:"operator_cancelled"});
            } else if (entry.priority === "background" && lanes.routine.length) {
              lanes.background.unshift(entry);
              continue;
            } else {
              active = entry;
              entry.resolve(await entry.run({queue_wait_ms:Math.max(0, now() - entry.queuedAt)}));
            }
          } catch (error) {
            entry.reject(error);
          } finally {
            if (lanes.background[0] !== entry) jobs.delete(entry.key);
            active = null;
          }
        }
      } finally {
        pumping = false;
      }
    }

    return {
      enqueue: function (task) {
        if (!task || typeof task.key !== "string" || !lanes[task.priority] || typeof task.run !== "function") {
          return Promise.reject(new Error("invalid acquisition queue task"));
        }
        if (jobs.has(task.key)) return jobs.get(task.key).promise;
        var entry = Object.assign({}, task, {queuedAt:now()});
        entry.promise = new Promise(function (resolve, reject) {entry.resolve=resolve;entry.reject=reject;});
        jobs.set(entry.key, entry);
        lanes[entry.priority].push(entry);
        Promise.resolve().then(pump);
        return entry.promise;
      },
      status: function () {
        var pending = lanes.routine.concat(lanes.background);
        var oldest = pending.length ? Math.min.apply(null, pending.map(function (entry) {return entry.queuedAt;})) : null;
        return {active:active ? active.key : null,
          pending:{routine:lanes.routine.length,background:lanes.background.length},
          oldest_wait_ms:oldest === null ? 0 : Math.max(0, now() - oldest),
          blocked_reason:lanes.background.length && (lanes.routine.length || active && active.priority === "routine")
            ? "waiting_for_priority_work" : null};
      },
    };
  }

  root.SAQueue = Object.freeze({create:create});
}(globalThis));
