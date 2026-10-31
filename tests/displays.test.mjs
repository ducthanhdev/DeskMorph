import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
} }).outputText).toString('base64');
const errors = compile(read('../src/commandError.ts'));
const tick = () => new Promise(resolve => setImmediate(resolve));
const snapshot = sequence => ({ epoch: 'native-epoch', sequence, revision: `native-epoch:${sequence}`,
  capabilities: { canRead: true, canSetPrimary: false, reason: 'display_recovery_unverified' },
  logicalMonitors: [], physicalMonitors: [], transaction: null });

test('display subscription precedes read, ignores stale responses, recovers after read errors and cleans up', async () => {
  const states = [], listeners = new Map(), stopped = [];
  let cleanup, slot = 0, resolveRead;
  globalThis.__displayHook = {
    useState(initial) { const i = slot++; states[i] = initial; return [initial, value => { states[i] = typeof value === 'function' ? value(states[i]) : value; }]; },
    useEffect(callback) { cleanup = callback(); },
    listen: async (event, callback) => { listeners.set(event, callback); return () => stopped.push(event); },
    invoke: async () => { assert.equal(listeners.size, 2); return new Promise(resolve => { resolveRead = resolve; }); },
  };
  let source = read('../src/hooks/useDisplays.ts')
    .replace(/import \{ useEffect, useState \} from .*;/, 'const { useEffect, useState } = globalThis.__displayHook;')
    .replace(/import \{ listen \} from .*;/, 'const { listen } = globalThis.__displayHook;')
    .replace(/import \{ invoke \} from .*;/, 'const { invoke } = globalThis.__displayHook;')
    .replace('"../commandError"', JSON.stringify(errors));
  try {
    const { useDisplays } = await import(compile(source));
    useDisplays(); await tick();
    listeners.get('deskmorph:display-state')({ payload: snapshot(2) });
    resolveRead(snapshot(1)); await tick();
    assert.equal(states[0].sequence, 2, 'A delayed initial read cannot overwrite a newer native event');
    listeners.get('deskmorph:display-state')({ payload: snapshot(1) });
    assert.equal(states[0].sequence, 2);
    listeners.get('deskmorph:display-read-error')({ payload: { code: 'display_read_failed', message: 'Private diagnostic' } });
    assert.equal(states[0], null, 'Do not show stale primary labels after a service failure');
    assert.match(states[1], /display_read_failed/);
    listeners.get('deskmorph:display-state')({ payload: snapshot(2) });
    assert.equal(states[0].sequence, 2); assert.equal(states[1], null);
    cleanup();
    listeners.get('deskmorph:display-state')({ payload: snapshot(3) });
    assert.equal(states[0].sequence, 2);
    assert.equal(stopped.length, 2);
  } finally { cleanup?.(); delete globalThis.__displayHook; }
});

test('display panel explains unavailable mutation, groups mirror outputs and routes system settings without applying primary', async () => {
  const state = snapshot(1), calls = [];
  state.logicalMonitors = [{ id: 'mirror', name: 'Laptop + External', connectors: ['eDP-1','HDMI-1'], primary: true, x: 0, y: 0, scale: 1 }];
  state.physicalMonitors = ['eDP-1','HDMI-1'].map(connector => ({ connector, logicalId: 'mirror', active: true, width: 1920, height: 1080, refreshHz: 60 }));
  state.physicalMonitors.push({ connector: 'DP-2', name: 'Inactive monitor', active: false, logicalId: null });
  globalThis.__displayPanel = {
    useState: initial => [initial, () => {}],
    useDisplays: () => ({ state, error: null, refresh: () => calls.push('refresh') }),
    useI18n: () => ({ t: key => key, language: 'en' }),
    useAsyncLifetime: () => ({ capture: () => ({ aborted: false }) }),
    invoke: async command => calls.push(command),
  };
  const jsx = compile('export const jsx=(type,props)=>({type,props}); export const jsxs=jsx; export const Fragment="Fragment";');
  const source = read('../src/components/studio/DisplaySettings.tsx')
    .replace(/import \{ (useState|useDisplays|useI18n|useAsyncLifetime|invoke) \} from .*;/g, 'const { $1 }=globalThis.__displayPanel;')
    .replace(/import \{ (ErrorText|Card) \} from .*;/g, 'const $1="$1";')
    .replace('"../../commandError"', JSON.stringify(errors));
  const module = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsx));
  function* nodes(value) { if (!value || typeof value !== 'object') return; yield value; for (const child of [value.props?.children].flat(Infinity)) yield* nodes(child); }
  try {
    const { DisplaySettings } = await import('data:text/javascript;base64,' + Buffer.from(module).toString('base64'));
    const tree = [...nodes(DisplaySettings())];
    assert.equal(tree.filter(n => n.type === 'li').length, 2, 'Mirror outputs appear as one group, with the inactive output separate');
    assert.ok(tree.some(n => n.type === 'ErrorText' && n.props.error === 'display_recovery_unverified'));
    const primary = tree.find(n => n.type === 'button' && n.props.children === 'displayAlreadyPrimary');
    assert.equal(primary.props.disabled, true);
    await tree.find(n => n.type === 'button' && n.props.children === 'displayOpenSettings').props.onClick();
    assert.deepEqual(calls, ['open_display_settings']);
  } finally { delete globalThis.__displayPanel; }
});
