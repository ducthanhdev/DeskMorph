import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText).toString('base64');
const errorUrl = compile(fs.readFileSync(new URL('../src/commandError.ts', import.meta.url), 'utf8'));
const messagesUrl = compile(fs.readFileSync(new URL('../src/i18n/messages.ts', import.meta.url), 'utf8'));
const { CommandError } = await import(errorUrl);
const { translate } = await import(messagesUrl);
const jsxUrl = compile('export const jsx=(type,props)=>({type,props}); export const jsxs=jsx; export const Fragment="Fragment";');
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function* nodes(tree) {
  if (!tree || typeof tree !== 'object') return;
  yield tree;
  const children = tree.props?.children;
  for (const child of Array.isArray(children) ? children.flat(Infinity) : [children]) yield* nodes(child);
}

test('system actions reflect missing capabilities, localize actionable errors, serialize requests and ignore inactive completion', async () => {
  const states = [], refs = [], requests = [], calls = [], cleanups = [];
  let stateIndex = 0, refIndex = 0, language = 'vi', active = true;
  let status = { monitorId: null, folderAvailable: false, trashAvailable: false };
  globalThis.__systemPopupTest = {
    useState(initial) { const index = stateIndex++; if (!(index in states)) states[index] = initial; return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }]; },
    useRef(initial) { const index = refIndex++; return refs[index] ||= { current: initial }; },
    useEffect(callback) { if (!cleanups.length) cleanups.push(callback()); },
    usePolling() {}, usePopupActive: () => active,
    useI18n: () => ({ t: key => translate(language, key), locale: language === 'vi' ? 'vi-VN' : 'en-US' }),
    useSystemStatus: () => ({ status, error: null }),
    invoke(command, args) { calls.push({ command, args }); const request = deferred(); requests.push(request); return request.promise; },
  };
  let source = fs.readFileSync(new URL('../src/components/SystemPopup.tsx', import.meta.url), 'utf8');
  source = source.replace('"../commandError"', JSON.stringify(errorUrl));
  for (const names of ['useEffect, useRef, useState', 'invoke', 'useI18n', 'usePolling', 'useSystemStatus', 'usePopupActive']) {
    source = source.replace(new RegExp(`import \\{ ${names} \\} from .*;`), `const { ${names} } = globalThis.__systemPopupTest;`);
  }
  const transpiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsxUrl));
  const { SystemPopup } = await import('data:text/javascript;base64,' + Buffer.from(transpiled).toString('base64'));
  const render = () => { stateIndex = refIndex = 0; return SystemPopup({ generation: 48 }); };
  const button = (tree, key) => [...nodes(tree)].find(node => node.type === 'button' && node.props.children === translate(language, key));
  const alert = tree => [...nodes(tree)].find(node => node.props?.role === 'alert')?.props.children;
  try {
    let tree = render();
    for (const key of ['downloads', 'trash', 'systemMonitor']) assert.equal(button(tree, key).props.disabled, true);
    for (const key of ['fileManagerMissing', 'trashUnavailable', 'systemMonitorMissing']) {
      assert.ok([...nodes(tree)].some(node => node.props?.children === translate(language, key)));
    }
    status = { monitorId: 'org.gnome.SystemMonitor.desktop', folderAvailable: true, trashAvailable: true };
    for (language of ['vi', 'en']) {
      for (const [key, location, code, errorKey] of [
        ['downloads', 'downloads', 'downloads_missing', 'downloadsMissing'],
        ['downloads', 'downloads', 'file_manager_missing', 'fileManagerMissing'],
        ['trash', 'trash', 'trash_unsupported', 'trashUnavailable'],
        ['systemMonitor', 'monitor', 'system_monitor_missing', 'systemMonitorMissing'],
      ]) {
        tree = render(); const before = calls.length;
        button(tree, key).props.onClick(); button(tree, key).props.onClick();
        assert.equal(calls.length, before + 1);
        assert.deepEqual(calls.at(-1), { command: 'open_system_location', args: { location } });
        tree = render();
        for (const action of ['downloads', 'trash', 'systemMonitor']) assert.equal(button(tree, action).props.disabled, true);
        requests.at(-1).reject(new CommandError(code, 'native diagnostic', 'open_system_location'));
        await flush(); tree = render();
        assert.equal(alert(tree), translate(language, errorKey));
        assert.equal(button(tree, key).props.disabled, false);
      }
    }
    tree = render(); button(tree, 'systemMonitor').props.onClick();
    requests.at(-1).reject(new CommandError('system_monitor_launch_failed', 'all candidates rejected', 'open_system_location'));
    await flush(); tree = render();
    assert.match(alert(tree), /Unable to open/); assert.match(alert(tree), /all candidates rejected/);
    button(tree, 'downloads').props.onClick(); render();
    active = false; render(); const beforeInactive = [...states];
    requests.at(-1).reject(new Error('late failure')); await flush();
    assert.deepEqual(states, beforeInactive, 'Inactive completion cannot add a stale error or reset UI');
    const count = calls.length; button(render(), 'downloads').props.onClick(); assert.equal(calls.length, count);
    for (const cleanup of cleanups) cleanup?.();
  } finally {
    delete globalThis.__systemPopupTest;
  }
});
