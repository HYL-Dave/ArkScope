import { createContext } from "react";
import type { DataScheduleController } from "./dataScheduleControls";

// Keep the shared identity stable when controls and their consumers hot-update.
export const DataScheduleControlsContext = createContext<DataScheduleController | null>(null);
