import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/dockAppearance.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { appearanceOf, dockMetrics, dockSurface, BUILTIN_PRESETS } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const defaults = JSON.parse(fs.readFileSync(new URL('../src/config/defaults.json', import.meta.url)));

test('presets preserve pins, lifecycle, monitor and widget preferences', () => {
  const original = { ...defaults, enabled: false, autoHide: true, monitor: 'external', language: 'en', clockSeconds: false, launcherShortcut: 'Ctrl+Super+K' };
  for (const preset of BUILTIN_PRESETS) {
    const updated = { ...original, ...preset.appearance };
    for (const field of ['pinnedApps', 'enabled', 'autoHide', 'monitor', 'keepDockOnClose', 'showClock', 'language', 'clockSeconds', 'launcherShortcut']) {
      assert.deepEqual(updated[field], original[field]);
    }
    assert.deepEqual(appearanceOf(updated), preset.appearance);
  }
});
test('shared preview and Dock metrics keep magnification inside their surface', () => {
  for (const height of [40, 52, 90]) for (const iconSize of [24, 36, 56]) {
    const config = { ...defaults, height, iconSize, maxMagnificationScale: 2 };
    const metrics = dockMetrics(config);
    assert.ok(metrics.iconSize * metrics.maxScale <= height - 8);
    assert.ok(metrics.maxScale >= 1);
    assert.equal(dockSurface(config).height, `${height}px`);
  }
});
