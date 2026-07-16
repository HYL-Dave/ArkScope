import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { installUiTokens } from "./ui/tokens";
import "./styles.css";
import "./shell/shell.css";
import "./ui/primitives.css";

installUiTokens(document.documentElement);

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("root element #root not found");

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
