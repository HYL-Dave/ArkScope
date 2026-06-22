export function shouldEndResearchReplay(run: { status: string }, hasMore: boolean): boolean {
  return ["succeeded", "failed", "cancelled", "interrupted"].includes(run.status) && !hasMore;
}
