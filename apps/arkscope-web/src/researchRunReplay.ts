export function shouldEndResearchReplay(run: { status: string }, hasMore: boolean): boolean {
  return ["succeeded", "failed", "cancelled", "interrupted"].includes(run.status) && !hasMore;
}

export function shouldApplyResearchEvent(
  run: { status: string; error_code?: string | null },
  event: { type: string; data: Record<string, unknown> },
): boolean {
  if (event.type === "done") return run.status === "succeeded";
  if (event.type === "error") {
    return ["failed", "cancelled", "interrupted"].includes(run.status)
      && (!run.error_code || event.data.code === run.error_code);
  }
  return true;
}
