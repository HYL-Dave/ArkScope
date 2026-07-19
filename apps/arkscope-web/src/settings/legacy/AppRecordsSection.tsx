import { useState } from "react";
import {
  applyAppRecordsMigration,
  previewAppRecordsMigration,
  type AppRecordsMigrationPreview,
  type AppRecordsMigrationResult,
} from "../../api";

// ---- App Records: PG→local migration (PG-exit 1c) — dry-run preview then explicit apply ----

const APP_RECORD_LABELS: Array<[string, string]> = [
  ["research_reports", "報告"],
  ["agent_memories", "記憶"],
  ["agent_queries", "查詢記錄"],
];

export function AppRecordsSection() {
  const [preview, setPreview] = useState<AppRecordsMigrationPreview | null>(null);
  const [applied, setApplied] = useState<AppRecordsMigrationResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "preview" | "apply">("");

  async function runPreview() {
    if (busy) return;
    setBusy("preview"); setErr(null); setApplied(null);
    try {
      setPreview(await previewAppRecordsMigration());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runApply() {
    if (busy || !preview?.would_apply) return;
    setBusy("apply"); setErr(null);
    try {
      setApplied(await applyAppRecordsMigration());
      setPreview(await previewAppRecordsMigration());  // refresh (now all idempotent)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  const totalConflicts = preview
    ? Object.values(preview.tables).reduce((n, t) => n + t.conflicts.length, 0) : 0;
  const totalMissing = preview
    ? Object.values(preview.tables).reduce((n, t) => n + t.missing_files.length, 0) : 0;
  const totalToInsert = preview
    ? Object.values(preview.tables).reduce((n, t) => n + t.to_insert.length, 0) : 0;
  const alreadyLocalized = !!preview && preview.would_apply && totalToInsert === 0;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>App Records 遷移 · reports / memories / queries</h2>
          <p className="muted tiny">
            把報告、記憶、查詢記錄從 PostgreSQL 一次性遷移到本地 profile_state.db。這些是不可再生的使用者/agent 資料。
            遷移<strong>保留原始 id</strong>（卡片→報告連結不會斷）、<strong>先備份本地 DB</strong>、衝突（同 id 不同內容）會拒絕不寫。
            先按「預覽」(dry-run，不寫入)，確認沒有衝突再「執行遷移」。遷移成功後才在他處啟用 use_local_records（本面板不提供切換）。
            需要 PG 可連線。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void runPreview()} disabled={!!busy}>
          {busy === "preview" ? "預覽中…" : "↻ 預覽 (dry-run)"}
        </button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!preview ? (
        <p className="muted">按「預覽」檢視 PG 與本地的差異（不會寫入）。</p>
      ) : (
        <div className="settings-panel">
          <table className="ds-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>表</th>
                <th style={{ textAlign: "right" }}>PG</th>
                <th style={{ textAlign: "right" }}>本地</th>
                <th style={{ textAlign: "right" }}>待遷移</th>
                <th style={{ textAlign: "right" }}>已存在</th>
                <th style={{ textAlign: "right" }}>衝突</th>
                <th style={{ textAlign: "right" }}>缺檔</th>
              </tr>
            </thead>
            <tbody>
              {APP_RECORD_LABELS.map(([key, label]) => {
                const t = preview.tables[key];
                if (!t) return null;
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    <td style={{ textAlign: "right" }}>{t.pg_count}</td>
                    <td style={{ textAlign: "right" }}>{t.local_count}</td>
                    <td style={{ textAlign: "right" }}>{t.to_insert.length}</td>
                    <td style={{ textAlign: "right" }}>{t.idempotent_skip.length}</td>
                    <td style={{ textAlign: "right", color: t.conflicts.length ? "var(--bad)" : undefined }}>
                      {t.conflicts.length}
                    </td>
                    <td style={{ textAlign: "right", color: t.missing_files.length ? "var(--warn, #b8860b)" : undefined }}>
                      {t.missing_files.length}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {alreadyLocalized && (
            <p className="tiny" style={{ marginTop: 8, color: "var(--ok)" }}>
              ✓ 已本地化：PG 與本地一致，無待遷移項目（reports/memories/queries 走 profile_state.db）。
            </p>
          )}
          {totalConflicts > 0 && (
            <p className="tiny refresh-err" style={{ marginTop: 8 }}>
              ✗ 有 {totalConflicts} 筆同 id 不同內容的衝突 — 遷移會被拒絕（不寫入）。請先排查再重試。
            </p>
          )}
          {totalMissing > 0 && (
            <p className="muted tiny" style={{ marginTop: 8 }}>
              ⚠ {totalMissing} 筆 file_path 找不到對應檔案（metadata 仍會遷移）。
            </p>
          )}

          <div className="settings-actions" style={{ marginTop: 12 }}>
            <button
              className="btn-ghost"
              onClick={() => void runApply()}
              disabled={!!busy || !preview.would_apply || totalToInsert === 0}
            >
              {busy === "apply" ? "遷移中…"
                : alreadyLocalized ? "已全部遷移"
                : `執行遷移 (apply) · ${totalToInsert} 筆`}
            </button>
            {!preview.would_apply && <span className="muted tiny">（有衝突，無法遷移）</span>}
          </div>

          {applied && (
            <p className="tiny" style={{ marginTop: 8, color: "var(--ok)" }}>
              ✓ 遷移完成：{APP_RECORD_LABELS.map(([k, l]) => {
                const r = applied.tables[k];
                return r ? `${l} +${r.inserted}（略過 ${r.skipped}）` : null;
              }).filter(Boolean).join("、")}。備份：{applied.backup ?? "—"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
