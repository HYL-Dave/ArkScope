// SSE frame parsing for the agent stream (POST /query/stream).
//
// The sidecar emits `data: {json}\n\n` per frame (src/agents/shared/events.py
// AgentEvent.to_sse, ensure_ascii=False). Frames arrive across arbitrary chunk
// boundaries over a 1–4 min turn, so parsing is stateful: push() buffers the
// trailing partial segment and only emits frames terminated by a blank line.
// A stray/keep-alive/malformed line is skipped, never crashing the stream.
//
// This is the load-bearing, I/O-free core; streamQuery() (api.ts) wraps it
// around fetch + a ReadableStream reader.

export interface SSEFrame {
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}

/** Parse one `\n\n`-delimited SSE segment into a frame, or null to skip it. */
function parseSegment(seg: string): SSEFrame | null {
  // Per the SSE spec a segment may carry several `data:` lines (joined with
  // \n); our server emits one. Non-data lines (`:` comments, event:/id:) skip.
  const dataParts: string[] = [];
  for (const rawLine of seg.split("\n")) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine; // tolerate CRLF
    if (line.startsWith("data:")) {
      const v = line.slice(5);
      dataParts.push(v.startsWith(" ") ? v.slice(1) : v); // drop one optional space
    }
  }
  if (dataParts.length === 0) return null;
  const payload = dataParts.join("\n").trim();
  if (!payload) return null;
  try {
    const obj = JSON.parse(payload);
    if (obj && typeof obj === "object" && typeof obj.type === "string") {
      return { type: obj.type, data: obj.data ?? {} };
    }
    return null; // well-formed JSON but not a frame → skip
  } catch {
    return null; // malformed JSON → skip, do not crash the stream
  }
}

export class SSEFrameParser {
  private buf = "";

  /** Feed decoded text; return every complete frame it now contains. */
  push(chunk: string): SSEFrame[] {
    this.buf += chunk;
    const segments = this.buf.split("\n\n");
    this.buf = segments.pop() ?? ""; // last piece is the incomplete remainder
    const out: SSEFrame[] = [];
    for (const seg of segments) {
      const frame = parseSegment(seg);
      if (frame) out.push(frame);
    }
    return out;
  }

  /** At stream end, emit a trailing frame whose blank-line terminator never came. */
  flush(): SSEFrame[] {
    const seg = this.buf;
    this.buf = "";
    const frame = parseSegment(seg);
    return frame ? [frame] : [];
  }
}
