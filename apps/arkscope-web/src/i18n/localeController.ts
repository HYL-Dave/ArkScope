import type { UiLocaleResponse } from "../api";
import { isUiLocale, type UiLocale } from "./locale";

export type { UiLocaleResponse } from "../api";

export interface UiLocaleAuthority {
  get(): Promise<UiLocaleResponse>;
  put(locale: UiLocale): Promise<UiLocaleResponse>;
}

export interface UiLocaleState {
  locale: UiLocale;
  busy: boolean;
  errorCode: "write_failed" | null;
}

export interface UiLocaleControllerOptions {
  initialLocale: UiLocale;
  authority: UiLocaleAuthority;
  applyLocale(locale: UiLocale): void;
  writeCache(locale: UiLocale): unknown;
}

export interface UiLocaleController {
  getSnapshot(): UiLocaleState;
  subscribe(listener: () => void): () => void;
  reconcile(): Promise<void>;
  setLocale(locale: UiLocale): Promise<boolean>;
}

function isUiLocaleResponse(value: unknown): value is UiLocaleResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<UiLocaleResponse>;
  return (
    isUiLocale(candidate.locale) &&
    (candidate.source === "default" || candidate.source === "stored")
  );
}

export function createUiLocaleController({
  initialLocale,
  authority,
  applyLocale,
  writeCache,
}: UiLocaleControllerOptions): UiLocaleController {
  let state: UiLocaleState = {
    locale: initialLocale,
    busy: false,
    errorCode: null,
  };
  let committedLocale = initialLocale;
  let operationSequence = 0;
  let reconciliation: Promise<void> | null = null;
  const listeners = new Set<() => void>();

  const emit = () => {
    for (const listener of listeners) listener();
  };

  const replaceState = (next: UiLocaleState) => {
    state = next;
    emit();
  };

  const cacheAfterAuthoritySuccess = (locale: UiLocale) => {
    try {
      writeCache(locale);
    } catch {
      // Cache is best-effort and never outranks the durable authority.
    }
  };

  const controller: UiLocaleController = {
    getSnapshot: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    reconcile() {
      if (reconciliation) return reconciliation;
      if (operationSequence > 0) {
        reconciliation = Promise.resolve();
        return reconciliation;
      }

      const sequence = ++operationSequence;
      reconciliation = authority
        .get()
        .then((response) => {
          if (sequence !== operationSequence || !isUiLocaleResponse(response)) return;
          committedLocale = response.locale;
          applyLocale(response.locale);
          if (state.locale !== response.locale || state.errorCode !== null) {
            replaceState({ locale: response.locale, busy: false, errorCode: null });
          }
          cacheAfterAuthoritySuccess(response.locale);
        })
        .catch(() => {
          // Startup is fail-open: bootstrap truth remains visible and usable.
        });
      return reconciliation;
    },
    async setLocale(locale) {
      if (state.busy) return false;

      const sequence = ++operationSequence;
      const rollbackLocale = committedLocale;
      applyLocale(locale);
      replaceState({ locale, busy: true, errorCode: null });

      try {
        const response = await authority.put(locale);
        if (
          sequence !== operationSequence ||
          !isUiLocaleResponse(response) ||
          response.source !== "stored" ||
          response.locale !== locale
        ) {
          throw new Error("invalid locale authority response");
        }
        committedLocale = locale;
        replaceState({ locale, busy: false, errorCode: null });
        cacheAfterAuthoritySuccess(locale);
        return true;
      } catch {
        if (sequence !== operationSequence) return false;
        applyLocale(rollbackLocale);
        replaceState({
          locale: rollbackLocale,
          busy: false,
          errorCode: "write_failed",
        });
        return false;
      }
    },
  };

  return controller;
}
