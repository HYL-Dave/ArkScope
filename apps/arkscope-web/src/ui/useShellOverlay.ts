import { useEffect, useState } from "react";
import { SHELL_OVERLAY_BREAKPOINT_PX, shellOverlayMediaQuery } from "./tokens";

export function shellOverlayMatches(width: number): boolean {
  return width <= SHELL_OVERLAY_BREAKPOINT_PX;
}

export function useShellOverlay(): boolean {
  const query = shellOverlayMediaQuery();
  const get = () => typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia(query).matches;
  const [matches, setMatches] = useState(get);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}
