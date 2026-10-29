import { ErrorText } from "../ErrorText";
import { useRemovalFocus } from "../../hooks/useRemovalFocus";
import { useEffect, useState } from "react";
import { useConfig } from "../../config/store";
import { appearanceOf, BUILTIN_PRESETS, type Appearance } from "../../dockAppearance";
import { useI18n } from "../../i18n/useI18n";
import { Card, Range, Toggle } from "./Controls";
export function AppearanceSettings() {
  const { config, updateConfig } = useConfig();
  const { t } = useI18n();
  const removalFocus = useRemovalFocus();
  const [colorDraft, setColorDraft] = useState(config.accentColor);
  useEffect(() => setColorDraft(config.accentColor), [config.accentColor]);
  const nameInput = removalFocus.fallback;
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [previous, setPrevious] = useState<Appearance | null>(null);
  const apply = async (appearance: Appearance) => { const before = appearanceOf(config); if (await updateConfig(appearance)) setPrevious(before); };
  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed) { setError(t("emptyName")); return; }
    if (config.presets.some((p) => p.id !== editing && p.name.toLocaleLowerCase() === trimmed.toLocaleLowerCase())) { setError(t("duplicateName")); return; }
    const presets = editing ? config.presets.map((p) => p.id === editing ? { ...p, name: trimmed } : p) : [...config.presets, { id: crypto.randomUUID(), name: trimmed, appearance: appearanceOf(config) }];
    if (await updateConfig({ presets })) { setName(""); setEditing(null); setError(""); }
  };
  return <div ref={removalFocus.root} onFocusCapture={removalFocus.onFocusCapture}>
    <Card title={t("appearanceTab")}>
      <form className="settings-inline" onSubmit={(event) => { event.preventDefault(); if (/^#[0-9a-fA-F]{6}$/.test(colorDraft)) void updateConfig({ accentColor: colorDraft }); }}><label className="settings-field">{t("accent")}<input aria-label={t("accent")} value={colorDraft} maxLength={7} pattern="#[0-9a-fA-F]{6}" required onChange={(event) => setColorDraft(event.target.value)} /></label><input className="accent-swatch" type="color" tabIndex={-1} aria-hidden="true" value={config.accentColor} onChange={(event) => void updateConfig({ accentColor: event.target.value })} /><button type="submit" aria-label={`${t("save")} ${t("accent")}`} disabled={!/^#[0-9a-fA-F]{6}$/.test(colorDraft) || colorDraft === config.accentColor}>{t("save")}</button></form>
      <Range label={t("opacity")} min={.2} max={1} step={.01} unit="" value={config.opacity} onChange={(opacity) => updateConfig({ opacity })} />
      <Range label={t("radius")} min={0} max={40} value={config.borderRadius} onChange={(borderRadius) => updateConfig({ borderRadius })} />
      <Toggle label={t("bounce")} value={config.bouncingLaunch !== false} onChange={(bouncingLaunch) => updateConfig({ bouncingLaunch })} />
      <Toggle label={t("shadow")} value={config.dynamicShadow !== false} onChange={(dynamicShadow) => updateConfig({ dynamicShadow })} />
      <Toggle label={t("magnify")} value={config.magnification !== false} onChange={(magnification) => updateConfig({ magnification })} />
      <Range label={t("maxScale")} min={1} max={2} step={.05} unit="×" value={config.maxMagnificationScale || 1.35} onChange={(maxMagnificationScale) => updateConfig({ maxMagnificationScale })} />
      <Toggle label={t("reduceMotion")} value={config.reduceMotion} onChange={(reduceMotion) => updateConfig({ reduceMotion })} />
    </Card>
    <Card title={t("presets")}>
      <p className="settings-help">{t("presetHelp")}</p>
      <div className="preset-grid">{BUILTIN_PRESETS.map((preset) => <button key={preset.id} className="preset-choice" onClick={() => void apply({ ...preset.appearance })}><span style={{ background: preset.appearance.accentColor }} />{t(preset.nameKey)}</button>)}</div>
      {previous && <button className="studio-button" onClick={async () => { if (await updateConfig(previous)) setPrevious(null); }}>{t("undo")}</button>}
      <h3>{t("customPresets")}</h3>
      {!config.presets.length && <p className="settings-help">{t("noPresets")}</p>}
      {config.presets.map((preset) => <div className="preset-saved" key={preset.id}><span>{preset.name}</span><button aria-label={`${t("apply")} ${preset.name}`} onClick={() => void apply(preset.appearance)}>{t("apply")}</button><button aria-label={`${t("rename")} ${preset.name}`} onClick={() => { setEditing(preset.id); setName(preset.name); nameInput.current?.focus(); nameInput.current?.select(); }}>{t("rename")}</button><button data-remove-focus aria-label={`${t("remove")} ${preset.name}`} onClick={() => void updateConfig({ presets: config.presets.filter((p) => p.id !== preset.id) })}>{t("remove")}</button></div>)}
      <form className="settings-inline" onSubmit={(event) => { event.preventDefault(); void save(); }}><input ref={nameInput} aria-label={t("presetName")} placeholder={t("presetName")} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} /><button className="studio-button" disabled={!editing && config.presets.length >= 32} type="submit">{editing ? t("rename") : t("savePreset")}</button>{editing && <button type="button" onClick={() => { setEditing(null); setName(""); nameInput.current?.focus(); }}>{t("cancel")}</button>}</form>
      {error && <p role="alert"><ErrorText error={error} /></p>}
    </Card>
  </div>;
}
