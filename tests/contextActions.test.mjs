import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText).toString('base64');
const jsx = compile('export const jsx=(type,props)=>({type,props});export const jsxs=jsx;export const Fragment="Fragment";');
function* nodes(tree) { if (!tree || typeof tree !== 'object') return; yield tree; for (const child of [tree.props?.children].flat(Infinity)) yield* nodes(child); }
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
test('context requests serialize synchronously, recover from failures and preserve popup generation after disposal', async () => {
  const states = [], refs = [], calls = [], requests = []; let si = 0, ri = 0;
  const controller = new AbortController();
  const request = (command, args) => {
    calls.push({ command, args });
    if (command === 'hide_dock_context_menu') return Promise.resolve(true);
    let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    requests.push({ resolve, reject }); return promise;
  };
  globalThis.__contextActions = {
    useState(initial) { const index = si++; if (!(index in states)) states[index] = initial; return [states[index], value => { states[index] = value; }]; },
    useRef(initial) { return refs[ri++] ||= { current: initial }; }, useEffect() {}, useLayoutEffect() {},
    invoke: request, usePopupFocus: () => ({}),
    useConfig: () => ({ config: { pinnedApps: [{ id: 'fixture' }] }, mutatePin: (...args) => request('mutatePin', args) }),
    usePlatform: () => ({ platform: { windows: { enumerate: true, activate: true, close: true }, forceQuit: true } }),
    useInstalledApps: () => ({ apps: [], loading: false, error: null }),
    useI18n: () => ({ t: key => key, pinName: () => 'fixture' }),
    useAsyncLifetime: () => ({ capture: () => controller.signal }),
    useLiveWindows: () => ({ windows: [], active: true }),
    desktopIsMissing: () => false, capabilityReason: () => 'unavailable',
  };
  let source = fs.readFileSync(new URL('../src/DockContextMenuStandalone.tsx', import.meta.url), 'utf8').split('export const DockContextMenuStandalone')[0];
  source = source.replace(/^import .*;\n/gm, '')
    .replace('function ContextActions(', 'export function ContextActions(');
  source = 'const {useEffect,useLayoutEffect,useRef,useState,invoke,usePopupFocus,useConfig,usePlatform,useInstalledApps,useI18n,useAsyncLifetime,useLiveWindows,desktopIsMissing,capabilityReason}=globalThis.__contextActions; const errorMessage=String; const ErrorText="ErrorText",AppIcon="AppIcon",ArrowLeft="ArrowLeft",ArrowRight="ArrowRight",Flame="Flame",Pin="Pin",PinOff="PinOff",Plus="Plus",X="X";\n' + source;
  const url = compile(source);
  const output = Buffer.from(url.split(',')[1], 'base64').toString().replaceAll('"react/jsx-runtime"', JSON.stringify(jsx));
  const { ContextActions } = await import('data:text/javascript;base64,' + Buffer.from(output).toString('base64'));
  const render = () => { si = ri = 0; return ContextActions({ menu: { appId: 'fixture', appName: 'fixture', command: 'desktop:fixture.desktop', isPinned: true, popupGeneration: 12 } }); };
  const button = (tree, label) => [...nodes(tree)].find(node => node.type === 'button' && [node.props.children].flat(Infinity).includes(label));
  try {
    let tree = render(); const launch = button(tree, 'newLaunch');
    launch.props.onClick(); launch.props.onClick(); button(tree, 'unpin').props.onClick();
    assert.equal(calls.length, 1, 'Launch and pin share one synchronous lock');
    assert.equal(button(render(), 'newLaunch').props.disabled, true);
    requests.at(-1).reject(new Error('launch failed')); await flush();
    tree = render(); assert.equal(button(tree, 'newLaunch').props.disabled, false);
    assert.match([...nodes(tree)].find(node => node.props?.role === 'alert').props.children.props.error, /launch failed/);
    button(tree, 'unpin').props.onClick(); button(tree, 'unpin').props.onClick();
    assert.equal(calls.filter(call => call.command === 'mutatePin').length, 1);
    requests.at(-1).resolve(false); await flush();
    assert.ok(!calls.some(call => call.command === 'hide_dock_context_menu'), 'Failed mutation keeps reviewable error popup');
    tree = render(); button(tree, 'unpin').props.onClick(); requests.at(-1).resolve(true); await flush();
    assert.deepEqual(calls.at(-1), { command: 'hide_dock_context_menu', args: { generation: 12 } });
    tree = render(); const before = calls.filter(call => call.command === 'hide_dock_context_menu').length;
    button(tree, 'newLaunch').props.onClick(); controller.abort(); requests.at(-1).resolve(true); await flush();
    assert.equal(calls.filter(call => call.command === 'hide_dock_context_menu').length, before, 'Late completion cannot close replacement popup');
  } finally { delete globalThis.__contextActions; }
});
