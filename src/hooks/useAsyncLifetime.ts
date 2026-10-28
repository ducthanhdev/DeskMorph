import { useEffect, useState } from "react";
import { AsyncLifetime } from "./asyncLifetime";
export function useAsyncLifetime() {
  const [lifetime] = useState(() => new AsyncLifetime());
  useEffect(() => { lifetime.start(); return () => lifetime.stop(); }, [lifetime]);
  return lifetime;
}
