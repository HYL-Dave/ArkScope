import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import type { UiLocale } from "./locale";
import type { UiLocaleController, UiLocaleState } from "./localeController";

export interface UiLocaleContextValue extends UiLocaleState {
  setLocale(locale: UiLocale): Promise<boolean>;
}

const UiLocaleContext = createContext<UiLocaleContextValue | null>(null);

export function LocaleProvider({
  controller,
  children,
}: {
  controller: UiLocaleController;
  children: ReactNode;
}) {
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );

  useEffect(() => {
    void controller.reconcile();
  }, [controller]);

  const value = useMemo<UiLocaleContextValue>(
    () => ({
      ...state,
      setLocale: (locale) => controller.setLocale(locale),
    }),
    [controller, state],
  );

  return <UiLocaleContext.Provider value={value}>{children}</UiLocaleContext.Provider>;
}

export function useUiLocale(): UiLocaleContextValue {
  const value = useContext(UiLocaleContext);
  if (!value) throw new Error("useUiLocale must be used within LocaleProvider");
  return value;
}
