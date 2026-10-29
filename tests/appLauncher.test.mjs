import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText).toString('base64');
const jsxUrl = compile('export const jsx = (type, props) => ({ type, props }); export const jsxs = jsx;');
const searchUrl = compile(fs.readFileSync(new URL('../src/appSearch.ts', import.meta.url), 'utf8'));
const lifetimeUrl = compile(fs.readFileSync(new URL('../src/hooks/asyncLifetime.ts', import.meta.url), 'utf8'));
const errorUrl = compile(fs.readFileSync(new URL('../src/commandError.ts', import.meta.url), 'utf8'));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
const app = (id, name) => ({ id, name, genericName: '', keywords: [], matchClasses: [], executable: '/bin/true', iconPath: null, actions: [] });
function* nodes(tree) { if (!tree || typeof tree !== 'object') return; yield tree; const children = tree.props?.children; for (const child of Array.isArray(children) ? children.flat(Infinity) : [children]) yield* nodes(child); }
const find = (tree, predicate) => [...nodes(tree)].find(predicate);

// Exercise the real component's handlers/state and real popup completion guard.
// React/DOM and IPC are controlled adapters; native input is verified separately.
test('launcher states, keyboard selection, pending Enter lock, failure retry and generation-safe close', async () => {
  const states = [], refs = []; let stateIndex = 0, refIndex = 0;
  let catalogue = { apps: [], loading: true, error: null, refresh() {} };
  const calls = [], requests = []; let active = true;
  const controller = new AbortController();
  globalThis.__launcherTest = {
    useState: initial => { const index = stateIndex++; if (!(index in states)) states[index] = initial; return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }]; },
    useRef: initial => { const index = refIndex++; return refs[index] ||= { current: initial }; },
    useEffect() {}, useMemo: callback => callback(),
    useInstalledApps: () => catalogue,
    useConfig: () => ({ config: { pinnedApps: [] }, mutatePin: assert.fail, error: null }),
    useI18n: () => ({ t: key => key, count: (_key, count) => String(count) }),
    useAsyncLifetime: () => ({ capture: () => controller.signal }),
    usePopupActive: () => active,
    invoke: (command, args) => { calls.push({ command, args }); if (command === 'hide_dock_context_menu') return Promise.resolve(true); const request = deferred(); requests.push(request); return request.promise; },
  };
  let source = fs.readFileSync(new URL('../src/components/AppLauncher.tsx', import.meta.url), 'utf8');
  source = source.replace(/import \{ useEffect, useMemo, useRef, useState \} from .*;/, 'const { useEffect, useMemo, useRef, useState } = globalThis.__launcherTest;')
    .replace(/import \{ invoke \} from .*;/, 'const { invoke } = globalThis.__launcherTest;')
    .replace(/import \{ Pin, PinOff, RefreshCw, Search, Settings \} from .*;/, 'const Pin="Pin", PinOff="PinOff", RefreshCw="RefreshCw", Search="Search", Settings="Settings";')
    .replace(/import \{ useInstalledApps \} from .*;/, 'const { useInstalledApps } = globalThis.__launcherTest;')
    .replace(/import \{ useConfig, errorMessage \} from .*;/, `const { useConfig } = globalThis.__launcherTest; import { errorMessage } from ${JSON.stringify(errorUrl)};`)
    .replace(/import \{ useI18n \} from .*;/, 'const { useI18n } = globalThis.__launcherTest;')
    .replace(/import \{ useAsyncLifetime \} from .*;/, 'const { useAsyncLifetime } = globalThis.__launcherTest;')
    .replace(/import \{ usePopupActive \} from .*;/, 'const { usePopupActive } = globalThis.__launcherTest;')
    .replace(/import \{ AppIcon \} from .*;/, 'const AppIcon="AppIcon";')
    .replaceAll('"../appSearch"', JSON.stringify(searchUrl)).replaceAll('"../hooks/asyncLifetime"', JSON.stringify(lifetimeUrl));
  // JSX runtime import is emitted by TypeScript, so replace it after transpiling.
  const transpiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsxUrl));
  const { AppLauncher } = await import('data:text/javascript;base64,' + Buffer.from(transpiled).toString('base64'));
  const render = () => { stateIndex = refIndex = 0; return AppLauncher({ generation: 73 }); };
  const hasMessage = (tree, key) => Boolean(find(tree, node => node.props?.children === key));
  const input = tree => find(tree, node => node.type === 'input');
  const key = (value, extra = {}) => ({ key: value, preventDefault() {}, ...extra });
  let tree = render(); assert.ok(hasMessage(tree, 'scanningApps')); assert.equal(hasMessage(tree, 'noApps'), false);
  catalogue = { ...catalogue, loading: false, error: 'scan error' };
  tree = render(); assert.ok(find(tree, node => node.props?.role === 'alert')); assert.equal(hasMessage(tree, 'noApps'), false);
  catalogue = { ...catalogue, error: null }; tree = render(); assert.ok(hasMessage(tree, 'noApps'));
  catalogue = { ...catalogue, apps: [app('a.desktop', 'Alpha'), app('b.desktop', 'Beta'), app('c.desktop', 'Gamma')] };
  tree = render(); tree.props.onKeyDown(key('ArrowUp')); tree = render();
  assert.equal(find(tree, node => node.props?.['aria-current'] === 'true').props['aria-label'], 'open Gamma');
  tree.props.onKeyDown(key('Home', { ctrlKey: true })); tree = render();
  tree.props.onKeyDown(key('ArrowDown')); tree = render();
  assert.equal(find(tree, node => node.props?.['aria-current'] === 'true').props['aria-label'], 'open Beta');
  input(tree).props.onKeyDown(key('Enter')); input(tree).props.onKeyDown(key('Enter')); input(tree).props.onKeyDown(key('Enter'));
  assert.equal(requests.length, 1); assert.deepEqual(calls[0], { command: 'launch_installed_app', args: { id: 'b.desktop', action: null } });
  tree = render(); assert.equal(find(tree, node => node.props?.['aria-label'] === 'open Beta').props.disabled, true);
  assert.ok(find(tree, node => node.props?.role === 'status' && node.props?.['aria-live'] === 'polite'));
  requests[0].reject(new Error('launch failed')); await flush();
  assert.equal(calls.filter(call => call.command === 'hide_dock_context_menu').length, 0);
  tree = render(); assert.ok(find(tree, node => node.props?.role === 'alert'));
  const retry = find(tree, node => node.type === 'button' && node.props?.children === 'retry');
  retry.props.onClick(); retry.props.onClick(); assert.equal(requests.length, 2);
  requests[1].resolve(true); await flush();
  assert.deepEqual(calls.at(-1), { command: 'hide_dock_context_menu', args: { generation: 73 } });
  tree = render(); tree.props.onKeyDown(key('End', { ctrlKey: true })); tree = render();
  input(tree).props.onKeyDown(key('Enter')); assert.equal(calls.at(-1).args.id, 'c.desktop');
  controller.abort(); requests[2].resolve(true); await flush();
  assert.equal(calls.filter(call => call.command === 'hide_dock_context_menu').length, 1, 'Disposed completion cannot close a replacement');
  active = false; input(render()).props.onKeyDown(key('Enter')); assert.equal(requests.length, 3);
  delete globalThis.__launcherTest;
});
