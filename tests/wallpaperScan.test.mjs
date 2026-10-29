import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText).toString('base64');
const jsxUrl = compile('export const jsx = (type, props) => ({type, props}); export const jsxs = jsx; export const Fragment = "Fragment";');
const errorUrl = compile(fs.readFileSync(new URL('../src/commandError.ts', import.meta.url), 'utf8'));
const capabilitiesUrl = compile(fs.readFileSync(new URL('../src/capabilities.ts', import.meta.url), 'utf8'));
const dateTimeUrl = compile(fs.readFileSync(new URL('../src/dateTime.ts', import.meta.url), 'utf8'));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function* nodes(tree) {
  if (!tree || typeof tree !== 'object') return;
  yield tree;
  const children = tree.props?.children;
  for (const child of Array.isArray(children) ? children.flat(Infinity) : [children]) yield* nodes(child);
}

test('wallpaper scan effects cancel only their request, ignore stale results, retry errors and suppress disposed completion', async () => {
  const states = [], refs = [], effects = [], pending = [], calls = [], scans = [];
  let stateIndex = 0, refIndex = 0, effectIndex = 0;
  let platform = { wallpaper: true };
  let config = { wallpaperFolders: ['/first'], wallpaperRecursive: true, wallpaperFavorites: [], wallpaperIntervalMinutes: 1 };
  globalThis.__wallpaperScanTest = {
    useState(initial) {
      const index = stateIndex++;
      if (!(index in states)) states[index] = initial;
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }];
    },
    useRef(initial) { const index = refIndex++; return refs[index] ||= { current: initial }; },
    useEffect(callback, deps) {
      const index = effectIndex++;
      if (!effects[index] || deps.some((dep, i) => !Object.is(dep, effects[index].deps[i]))) {
        pending.push(() => { effects[index]?.cleanup?.(); effects[index] = { deps, cleanup: callback() }; });
      }
    },
    usePolling() {},
    useConfig: () => ({ config, updateConfig: assert.fail }),
    usePlatform: () => ({ platform }),
    useI18n: () => ({ t: key => key, locale: 'vi-VN' }),
    convertFileSrc: path => path,
    invoke(command, args) {
      calls.push({ command, args });
      if (command === 'scan_wallpapers') { const request = deferred(); scans.push(request); return request.promise; }
      assert.ok(['cancel_wallpaper_scan', 'wallpaper_thumbnails'].includes(command));
      return Promise.resolve(command === 'wallpaper_thumbnails' ? [] : undefined);
    },
  };
  let source = fs.readFileSync(new URL('../src/components/studio/WallpaperSettings.tsx', import.meta.url), 'utf8');
  for (const names of ['useEffect, useRef, useState', 'convertFileSrc', 'invoke', 'usePlatform', 'usePolling', 'useI18n']) {
    source = source.replace(new RegExp(`import \\{ ${names} \\} from .*;`), `const { ${names} } = globalThis.__wallpaperScanTest;`);
  }
  source = source.replace(/import \{ useConfig, errorMessage \} from .*;/,
    `const { useConfig } = globalThis.__wallpaperScanTest; import { errorMessage } from ${JSON.stringify(errorUrl)};`)
    .replace(/import \{ Card, Toggle \} from .*;/, 'const Card="Card", Toggle="Toggle";')
    .replaceAll('"../../dateTime"', JSON.stringify(dateTimeUrl))
    .replaceAll('"../../capabilities"', JSON.stringify(capabilitiesUrl));
  const transpiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsxUrl));
  const { WallpaperSettings } = await import('data:text/javascript;base64,' + Buffer.from(transpiled).toString('base64'));
  const render = () => {
    stateIndex = refIndex = effectIndex = 0;
    const tree = WallpaperSettings();
    for (const commit of pending.splice(0)) commit();
    return tree;
  };
  const click = (tree, label) => {
    const button = [...nodes(tree)].find(node => node.type === 'button' && node.props.children === label);
    assert.ok(button, `Missing ${label} button`); button.props.onClick();
  };
  try {
    render();
    const first = calls.find(call => call.command === 'scan_wallpapers').args.requestId;
    config = { ...config, wallpaperFolders: ['/second'] }; render();
    const second = calls.filter(call => call.command === 'scan_wallpapers')[1].args.requestId;
    assert.notEqual(first, second);
    assert.deepEqual(calls.find(call => call.command === 'cancel_wallpaper_scan').args, { requestId: first });
    scans[1].resolve({ images: [{ path: '/second/new.png', filename: 'new.png', folder: '/second', format: 'png' }], issues: [], limited: false });
    await flush(); render(); await flush();
    const beforeStale = [...states];
    scans[0].resolve({ images: [{ path: '/first/stale.png', filename: 'stale.png', folder: '/first', format: 'png' }], issues: [], limited: false });
    await flush(); assert.deepEqual(states, beforeStale, 'Old completion/finally cannot replace scan or loading state');
    let tree = render();
    assert.ok([...nodes(tree)].some(node => node.props?.['aria-label'] === 'apply new.png'));
    assert.ok(![...nodes(tree)].some(node => node.props?.['aria-label'] === 'apply stale.png'));
    platform = { wallpaper: false, unavailableReasons: { wallpaper: 'wallpaper_read_only' } };
    tree = render();
    const apply = [...nodes(tree)].find(node => node.props?.['aria-label'] === 'apply new.png');
    assert.equal(apply.props.disabled, true);
    const priorCalls = calls.length;
    await apply.props.onClick();
    assert.equal(calls.length, priorCalls, 'Unsupported handler cannot dispatch wallpaper apply even if invoked directly');
    assert.ok([...nodes(tree)].some(node => node.props?.role === 'status' && node.props.children === 'wallpaperReadOnly'));
    platform = { wallpaper: true }; tree = render();
    click(tree, 'scan'); render();
    assert.deepEqual(calls.filter(call => call.command === 'cancel_wallpaper_scan')[1].args, { requestId: second });
    scans[2].reject(new Error('permission denied')); await flush(); tree = render();
    assert.ok([...nodes(tree)].some(node => node.props?.role === 'alert' && node.props.children?.includes('permission denied')));
    click(tree, 'retry'); render();
    const beforeDispose = [...states];
    for (const effect of effects) effect.cleanup?.();
    scans[3].resolve({ images: [], issues: [], limited: false }); await flush();
    assert.deepEqual(states, beforeDispose, 'Unmounted scan completion cannot publish or clear state');
    assert.equal(calls.filter(call => call.command === 'cancel_wallpaper_scan').length, 4);
    assert.ok(calls.every(call => ['scan_wallpapers', 'cancel_wallpaper_scan', 'wallpaper_thumbnails'].includes(call.command)));
  } finally {
    delete globalThis.__wallpaperScanTest;
  }
});
