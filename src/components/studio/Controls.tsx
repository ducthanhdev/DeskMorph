import type { ReactNode } from "react";
export function Toggle({ label, value, onChange, help, disabled = false }: { label: string; value: boolean; onChange: (value: boolean) => unknown; help?: string; disabled?: boolean }) {
  return <label className="settings-toggle"><span>{label}{help && <small>{help}</small>}</span><input type="checkbox" checked={value} disabled={disabled} onChange={(e) => void onChange(e.target.checked)} /></label>;
}
export function Range({ label, value, min, max, step = 1, onChange, unit = "px" }: { label: string; value: number; min: number; max: number; step?: number; onChange: (value: number) => unknown; unit?: string }) {
  return <label className="settings-range"><span>{label}<output>{Number(value.toFixed(2))}{unit}</output></span><input type="range" aria-label={label} min={min} max={max} step={step} value={value} onChange={(e) => void onChange(Number(e.target.value))} /></label>;
}
export function Card({ title, children }: { title: string; children: ReactNode }) { return <section className="studio-card"><h2>{title}</h2>{children}</section>; }
