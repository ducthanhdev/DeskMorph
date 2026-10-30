import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText).toString('base64');
const jsx = compile('export const jsx=(type,props)=>({type,props});export const jsxs=jsx;export const Fragment="Fragment";');
function* nodes(tree) { if (!tree || typeof tree !== 'object') return; yield tree; for (const child of [tree.props?.children].flat(Infinity)) yield* nodes(child); }
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
test('context requests serialize synchronously, recover from failures and preserve popup generation after disposal', async () => {
  const states = [], refs = [], calls = [], requests = []; let si = 0, ri = 0, effects = [], language = 'vi';
  const controller = new AbortController();
  let visibleWindows = [];
  const originalDocument = globalThis.document;
  globalThis.document = { hasFocus: () => false };
  const request = (command, args) => {
    calls.push({ command, args });
    if (command === 'hide_dock_context_menu' || command === 'announce_accessibility') return Promise.resolve(true);
    let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    requests.push({ resolve, reject }); return promise;
  };
  globalThis.__contextActions = {
    useState(initial) { const index = si++; if (!(index in states)) states[index] = initial; return [states[index], value => { states[index] = value; }]; },
    useId() { return 'context-id-' + si++; },
    useRef(initial) { return refs[ri++] ||= { current: initial }; }, useEffect(callback) { effects.push(callback); }, useLayoutEffect() {},
    invoke: request, usePopupFocus: () => ({}),
    useConfig: () => ({ config: { pinnedApps: [{ id: 'fixture' }] }, mutatePin: (...args) => request('mutatePin', args) }),
    usePlatform: () => ({ platform: { windows: { enumerate: true, activate: true, close: true }, forceQuit: true } }),
    useInstalledApps: () => ({ apps: [], loading: false, error: null }),
    useI18n: () => ({ language, t: key => key, pinName: () => 'fixture' }),
    describeError: (locale, raw) => ({ summary: locale + ': ' + raw }),
    useAsyncLifetime: () => ({ capture: () => controller.signal }),
    useLiveWindows: () => ({ windows: visibleWindows, active: true }),
    desktopIsMissing: () => false, capabilityReason: () => 'unavailable',
  };
  let source = fs.readFileSync(new URL('../src/DockContextMenuStandalone.tsx', import.meta.url), 'utf8').split('export const DockContextMenuStandalone')[0];
  source = source.replace(/^import .*;\n/gm, '')
    .replace('function ContextActions(', 'export function ContextActions(');
  source = 'const {useEffect,useId,useLayoutEffect,useRef,useState,invoke,usePopupFocus,useConfig,usePlatform,useInstalledApps,useI18n,useAsyncLifetime,useLiveWindows,desktopIsMissing,capabilityReason,describeError}=globalThis.__contextActions; const errorMessage=String; const ErrorText="ErrorText",AppIcon="AppIcon",ArrowLeft="ArrowLeft",ArrowRight="ArrowRight",Flame="Flame",Pin="Pin",PinOff="PinOff",Plus="Plus",X="X";\n' + source;
  const url = compile(source);
  const output = Buffer.from(url.split(',')[1], 'base64').toString().replaceAll('"react/jsx-runtime"', JSON.stringify(jsx));
  const { ContextActions } = await import('data:text/javascript;base64,' + Buffer.from(output).toString('base64'));
  const render = () => { si = ri = 0; effects = []; const tree = ContextActions({ menu: { appId: 'fixture', appName: 'fixture', command: 'desktop:fixture.desktop', isPinned: true, windowId: 1, popupGeneration: 12 } }); effects.forEach(effect => effect()); return tree; };
  const button = (tree, label) => [...nodes(tree)].find(node => node.type === 'button' && [node.props.children].flat(Infinity).includes(label));
  try {
    let tree = render(); const launch = button(tree, 'newLaunch');
    const feedbackId = [...nodes(tree)].find(node => node.props?.role === 'alert').props.id;
    assert.ok(feedbackId, 'Live feedback region exists before the error');
    launch.props.onClick(); launch.props.onClick(); button(tree, 'unpin').props.onClick();
    assert.equal(calls.length, 1, 'Launch and pin share one synchronous lock');
    assert.equal(button(render(), 'newLaunch').props.disabled, true);
    requests.at(-1).reject(new Error('launch failed')); await flush();
    tree = render(); assert.equal(button(tree, 'newLaunch').props.disabled, false);
    const feedback = [...nodes(tree)].find(node => node.props?.role === 'alert');
    assert.equal(feedback.props.id, feedbackId);
    assert.equal(button(tree, 'newLaunch').props['aria-describedby'], [...nodes(feedback)].find(node => node.type === 'ErrorText').props.summaryId);
    assert.match([...nodes(feedback)].find(node => node.type === 'ErrorText').props.error, /launch failed/);
    const announcements = () => calls.filter(call => call.command === 'announce_accessibility');
    assert.deepEqual(announcements().map(call => call.args), [{ message: 'vi: Error: launch failed', generation: 12 }]);
    render(); render();
    assert.equal(announcements().length, 1, 'Rerenders/StrictMode effect replay do not duplicate an announcement');
    language = 'en'; tree = render();
    assert.equal(announcements().at(-1).args.message, 'en: Error: launch failed', 'Visible error follows the selected locale');
    button(tree, 'newLaunch').props.onClick();
    requests.at(-1).reject(new Error('launch failed')); await flush();
    tree = render();
    assert.equal(announcements().length, 3, 'Retrying the same error announces again even if the empty state was batched');


    button(tree, 'unpin').props.onClick(); button(tree, 'unpin').props.onClick();
    assert.equal(calls.filter(call => call.command === 'mutatePin').length, 1);
    requests.at(-1).resolve(false); await flush();
    assert.ok(!calls.some(call => call.command === 'hide_dock_context_menu'), 'Failed mutation keeps reviewable error popup');
    tree = render(); button(tree, 'unpin').props.onClick(); requests.at(-1).resolve(true); await flush();
    assert.deepEqual(calls.at(-1), { command: 'hide_dock_context_menu', args: { generation: 12 } });
    tree = render(); const before = calls.filter(call => call.command === 'hide_dock_context_menu').length;
    button(tree, 'newLaunch').props.onClick(); controller.abort(); requests.at(-1).resolve(true); await flush();
    assert.equal(calls.filter(call => call.command === 'hide_dock_context_menu').length, before, 'Late completion cannot close replacement popup');
    visibleWindows = [{ id: 1, title: 'fixture' }];
    tree = render(); button(tree, 'forceQuit').props.onClick(); tree = render();
    const review = [...nodes(tree)].find(node => node.props?.role === 'alertdialog');
    const warning = [...nodes(review)].find(node => node.props?.id === review.props['aria-describedby']);
    assert.equal(warning.props.children, 'forceWarning');
    for (const label of ['cancel', 'forceConfirm']) {
      assert.equal(button(review, label).props['aria-describedby'], warning.props.id);
    }
    const count = calls.length; button(review, 'cancel').props.onClick();
    assert.ok(![...nodes(render())].some(node => node.props?.role === 'alertdialog'));
    assert.equal(calls.length, count, 'Cancelling the described warning does not issue a force request');
  } finally { delete globalThis.__contextActions; if (originalDocument === undefined) delete globalThis.document; else globalThis.document = originalDocument; }
});
