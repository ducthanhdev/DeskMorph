import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText).toString('base64');
const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };

test('capability reasons distinguish loading, probe errors, unsupported adapters and development in both languages', async () => {
  const { capabilityReason } = await import(compile(read('../src/capabilities.ts')));
  const { messages } = await import(compile(read('../src/i18n/messages.ts')));
  for (const language of ['vi', 'en']) {
    const t = key => { assert.ok(messages[language][key]); return messages[language][key]; };
    assert.equal(capabilityReason(null, 'wallpaper', t), t('loading'));
    assert.equal(capabilityReason(null, 'wallpaper', t, 'offline'), t('capabilityProbeFailed'));
    for (const [feature, code, key] of [
      ['wallpaper', 'wallpaper_read_only', 'wallpaperReadOnly'],
      ['wallpaper', 'wallpaper_adapter_unsupported', 'wallpaperAdapterUnavailable'],
      ['windowEnumeration', 'xprop_unavailable', 'xpropMissing'],
      ['autoHide', 'dock_autohide_unverified', 'autoHideUnavailable'],
      ['workspaces', 'workspaces_not_implemented', 'workspacesDevelopment'],
    ]) assert.equal(capabilityReason({ unavailableReasons: { [feature]: code } }, feature, t), t(key));
    assert.equal(capabilityReason({ unavailableReasons: { wallpaper: 'future_code' } }, 'wallpaper', t), t('capabilityProbeFailed'));
  }
});

test('platform refresh coalesces events, revokes stale capability on failure and recovers without publishing after disposal', async () => {
  const states = [], requests = [], listeners = [], commands = [];
  let index = 0, effect, cleanup, deps, nextDeps, stopped = 0;
  globalThis.__platformTest = {
    useState(initial) { const slot = index++; if (!(slot in states)) states[slot] = initial; return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }]; },
    useEffect(callback, values) { if (!deps || values.some((value, i) => value !== deps[i])) { effect = callback; nextDeps = values; } },
    listen: async (_, callback) => { listeners.push(callback); return () => { stopped++; }; },
    invoke(command) { commands.push(command); if (command === 'refresh_platform_info') return Promise.resolve(); const request = deferred(); requests.push(request); return request.promise; },
  };
  let source = read('../src/hooks/usePlatform.ts')
    .replace(/import \{ useEffect, useState \} from .*;/, 'const { useEffect, useState } = globalThis.__platformTest;')
    .replace(/import \{ listen \} from .*;/, 'const { listen } = globalThis.__platformTest;')
    .replace(/import \{ invoke \} from .*;/, 'const { invoke } = globalThis.__platformTest;')
    .replace('"../config/store"', JSON.stringify(compile(read('../src/commandError.ts'))));
  const { usePlatform } = await import(compile(source));
  const render = () => { index = 0; effect = null; const result = usePlatform(); if (effect) { cleanup?.(); deps = nextDeps; cleanup = effect(); } return result; };
  try {
    render(); await flush(); requests[0].resolve({ wallpaper: true }); await flush();
    assert.equal(render().platform.wallpaper, true);
    listeners[0](); listeners[0](); listeners[0](); assert.equal(requests.length, 2);
    requests[1].reject(new Error('probe disconnected')); await flush();
    assert.equal(render().platform, null); assert.match(render().error, /probe disconnected/);
    assert.equal(requests.length, 3);
    requests[2].resolve({ wallpaper: false }); await flush();
    let value = render(); assert.equal(value.platform.wallpaper, false); assert.equal(value.error, null);
    listeners[0](); value.refresh(); render(); await flush();
    assert.ok(commands.includes('refresh_platform_info')); assert.equal(stopped, 1);
    requests[3].resolve({ wallpaper: true }); await flush();
    assert.equal(render().platform.wallpaper, false, 'Disposed effect must not grant old capabilities');
    requests[4].resolve({ wallpaper: true }); await flush(); assert.equal(render().platform.wallpaper, true);
    listeners[1](); cleanup(); const before = [...states];
    requests[5].reject(new Error('late error')); await flush(); listeners[1]();
    assert.deepEqual(states, before); assert.equal(requests.length, 6); assert.equal(stopped, 2);
  } finally { delete globalThis.__platformTest; }
});
