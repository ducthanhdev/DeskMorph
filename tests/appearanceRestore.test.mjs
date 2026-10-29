import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
} }).outputText).toString('base64');
const jsx = compile('export const jsx=(type,props)=>({type,props}); export const jsxs=jsx; export const Fragment="Fragment";');
function* nodes(value) {
  if (!value || typeof value !== 'object') return;
  yield value;
  for (const child of [value.props?.children].flat(Infinity)) yield* nodes(child);
}

test('Studio restore captures first ready appearance, survives tab/config changes, retries failed saves and patches no unrelated fields', async () => {
  const defaults = JSON.parse(read('../src/config/defaults.json'));
  const states = [], effects = [], pending = [], patches = [];
  let stateIndex = 0, effectIndex = 0, ready = false, config = defaults, succeed = false;
  globalThis.__restoreTest = {
    useState(initial) { const slot = stateIndex++; if (!(slot in states)) states[slot] = initial; return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }]; },
    useEffect(callback, deps) { const slot = effectIndex++; if (!effects[slot] || deps.some((value, i) => value !== effects[slot].deps[i])) pending.push(() => { effects[slot]?.cleanup?.(); effects[slot] = { deps, cleanup: callback() }; }); },
    useConfig: () => ({ config, ready, updateConfig: async patch => { patches.push(patch); if (succeed) config = { ...config, ...patch }; return succeed; } }),
    useAsyncLifetime: () => ({ capture: () => ({ aborted: false }) }),
    usePlatform: () => ({ platform: null }), useI18n: () => ({ t: key => key }),
  };
  let source = read('../src/Studio.tsx').replace(/import \{ useEffect, useState \} from .*;/, 'const { useEffect, useState }=globalThis.__restoreTest;')
    .replace(/import \{ (useConfig|usePlatform|useI18n|useAsyncLifetime) \} from .*;/g, 'const { $1 }=globalThis.__restoreTest;')
    .replace(/import \{ (Sparkles|DockSettings|AppsSettings|AppearanceSettings|SystemSettings|WallpaperSettings|DockPreview) \} from .*;/g, 'const $1="$1";')
    .replace('"./dockAppearance"', JSON.stringify(compile(read('../src/dockAppearance.ts'))));
  source = source.replace(/import \{ ErrorText \} from .*;/, 'const ErrorText="ErrorText";');
  source = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsx));
  const { Studio } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
  const render = () => { stateIndex = effectIndex = 0; const result = Studio(); for (const commit of pending.splice(0)) commit(); return result; };
  const restore = tree => [...nodes(tree)].find(node => node.type === 'button' && node.props.children === 'restoreAppearance');
  try {
    render(); assert.equal(states[1], null, 'Loading defaults cannot become the startup checkpoint');
    config = { ...defaults, height: 64, opacity: .7 }; ready = true;
    render(); assert.equal(restore(render()).props.disabled, true);
    const initial = states[1];
    config = { ...config, height: 40, opacity: .2, pinnedApps: [], autoHide: true, language: 'en' };
    let tree = render(); assert.equal(restore(tree).props.disabled, false);
    const tab = [...nodes(tree)].find(node => node.type === 'button' && node.props.children === 'appearanceTab');
    tab.props.onClick(); tree = render(); assert.equal(states[1], initial);
    await restore(tree).props.onClick(); tree = render();
    assert.equal(restore(tree).props.disabled, false, 'Failed restore remains retryable');
    assert.equal(config.height, 40);
    succeed = true; await restore(tree).props.onClick(); tree = render();
    assert.equal(restore(tree).props.disabled, true);
    assert.equal(config.height, 64); assert.equal(config.opacity, .7);
    assert.deepEqual(config.pinnedApps, []); assert.equal(config.autoHide, true); assert.equal(config.language, 'en');
    assert.deepEqual(patches, [initial, initial]);
    assert.ok(patches.every(patch => !('pinnedApps' in patch) && !('autoHide' in patch) && !('language' in patch)));
  } finally { for (const effect of effects) effect.cleanup?.(); delete globalThis.__restoreTest; }
});
