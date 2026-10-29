import { useEffect, useState } from "react";
export function useReducedMotion(preference: boolean) {
  const [system, setSystem] = useState(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const query = matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => setSystem(query.matches);
    query.addEventListener("change", changed);
    return () => query.removeEventListener("change", changed);
  }, []);
  return preference || system;
}
