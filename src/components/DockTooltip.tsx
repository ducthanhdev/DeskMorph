import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
export function DockTooltip() {
  const [text, setText] = useState("");
  useEffect(() => {
    let disposed = false;
    let stop: (() => void) | undefined;
    listen<string>("deskmorph:tooltip", (event) => { if (!disposed) setText(event.payload); })
      .then((unlisten) => { if (disposed) unlisten(); else stop = unlisten; }).catch(console.error);
    return () => { disposed = true; stop?.(); };
  }, []);
  return <div className="dock-tooltip-card" role="tooltip">{text}</div>;
}
