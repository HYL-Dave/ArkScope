import { useCallback, useEffect, useRef, useState } from "react";
import { getSecurityLifecycleAutomationStatus, runSecurityLifecycleCaseAutomation,
  type SecurityLifecycleAutomationStatusResponse } from "../api";

type PendingCheck = { caseId: string; requestId: string | null; baseline: string | null };
function isRunning(status: SecurityLifecycleAutomationStatusResponse | null) {
  return status?.last_status === "running" || Boolean(status?.current_progress.length);
}

export function useLifecycleSourceCheck(onComplete: () => void) {
  const [status, setStatus] = useState<SecurityLifecycleAutomationStatusResponse | null>(null);
  const [readFailed, setReadFailed] = useState(false);
  const [pending, setPending] = useState<PendingCheck | null>(null);
  const [dispatching, setDispatching] = useState(false);
  const [error, setErrorCode] = useState<"unavailable" | "unknown" | null>(null);
  const complete = useRef(onComplete); complete.current = onComplete;
  const sequence = useRef(0);
  const pendingRef = useRef<PendingCheck | null>(null);
  const statusRef = useRef<SecurityLifecycleAutomationStatusResponse | null>(null);
  const dispatchLock = useRef(false);
  const mounted = useRef(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const read = async () => {
      const token = ++sequence.current;
      let keepPolling = pendingRef.current !== null || isRunning(statusRef.current);
      try {
        const value = await getSecurityLifecycleAutomationStatus();
        if (cancelled || token !== sequence.current) return;
        const wasRunning = isRunning(statusRef.current);
        setStatus(value); statusRef.current = value; setReadFailed(false);
        const active = isRunning(value);
        keepPolling = active || pendingRef.current !== null;
        const request = pendingRef.current;
        if (request) {
          const belongs = value.last_result?.case_ids.includes(request.caseId)
            || Boolean(value.active_incident?.case_failures[request.caseId]) || Boolean(value.active_incident?.scheduler_failure);
          const observed = value.schedule.last_attempt_at;
          const newer = observed !== null && (request.baseline === null || Date.parse(observed) > Date.parse(request.baseline));
          if (!active && value.telemetry_status === "valid" && newer && belongs) {
            pendingRef.current = null; setPending(null); setErrorCode(null); keepPolling = false;
            complete.current();
          }
        } else if (wasRunning && !active && value.telemetry_status === "valid") {
          complete.current();
        }
      } catch { if (!cancelled && token === sequence.current) setReadFailed(true); }
      if (!cancelled && keepPolling) timer = setTimeout(() => { void read(); }, 2000);
    };
    void read();
    return () => { cancelled = true; clearTimeout(timer); sequence.current += 1; };
  }, [revision]);

  const start = useCallback(async (caseId: string) => {
    if (pendingRef.current || dispatchLock.current) return;
    dispatchLock.current = true;
    setDispatching(true); setErrorCode(null);
    const baseline = statusRef.current?.schedule.last_attempt_at ?? null;
    function watch(requestId: string | null) {
      const request = { caseId, requestId, baseline };
      pendingRef.current = request; setPending(request); setRevision((value) => value + 1);
    }
    try {
      const result = await runSecurityLifecycleCaseAutomation(caseId);
      if (!mounted.current) return;
      if (result.status !== "started") { setErrorCode("unavailable"); return; }
      if (!result.request_id) { setErrorCode("unknown"); watch(null); return; }
      watch(result.request_id);
    } catch { if (mounted.current) { setErrorCode("unknown"); watch(null); } }
    finally { dispatchLock.current = false; if (mounted.current) setDispatching(false); }
  }, []);
  return { status, readFailed, busy: dispatching || pending !== null, error: error !== null, outcomeUnknown: error === "unknown",
    start, refresh: () => setRevision((value) => value + 1) };
}
