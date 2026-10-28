import { useState } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { AppWindow } from "lucide-react";
export function AppIcon({ path, size = 24 }: { path?: string | null; size?: number }) {
  const [failed, setFailed] = useState<string | null>(null);
  return path && failed !== path ? <img src={convertFileSrc(path)} width={size} height={size} alt="" draggable={false} onError={() => setFailed(path)} /> : <AppWindow size={size} aria-hidden="true" />;
}
