import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText).toString('base64');
const errorUrl = compile(fs.readFileSync(new URL('../src/commandError.ts', import.meta.url), 'utf8'));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };

test('catalogue errors retain the last apps, coalesce refresh, and never mutate pins or publish after disposal', async () => {
  const state = []; let effect, receive, stopped = 0;
  const calls = [], requests = [];
  globalThis.__installedAppsTest = {
    useState: initial => { const index = state.length; state.push(initial); return [initial, value => { state[index] = typeof value === 'function' ? value(state[index]) : value; }]; },
    useEffect: callback => { effect = callback; },
    useCallback: callback => callback,
    listen: async (event, callback) => { assert.equal(event, 'deskmorph:apps-changed'); receive = callback; return () => { stopped++; }; },
    invoke: (command, args) => { calls.push({ command, args }); const request = deferred(); requests.push(request); return request.promise; },
  };
  let source = fs.readFileSync(new URL('../src/hooks/useInstalledApps.ts', import.meta.url), 'utf8');
  source = source.replace(/import \{ useCallback, useEffect, useState \} from .*;/, 'const { useCallback, useEffect, useState } = globalThis.__installedAppsTest;')
    .replace(/import \{ invoke \} from .*;/, 'const { invoke } = globalThis.__installedAppsTest;')
    .replace(/import \{ listen \} from .*;/, 'const { listen } = globalThis.__installedAppsTest;')
    .replace('"../config/store"', JSON.stringify(errorUrl));
  const { useInstalledApps } = await import(compile(source));
  useInstalledApps(); const dispose = effect(); await flush();
  const original = [{ id: 'kept.desktop', name: 'Kept' }];
  requests[0].resolve(original); await flush();
  assert.equal(state[0], original); assert.equal(state[1], false); assert.equal(state[2], null);
  receive(); receive(); receive();
  assert.equal(requests.length, 2, 'Concurrent events must share the active request');
  requests[1].reject(new Error('temporary scan failure')); await flush();
  assert.equal(state[0], original, 'A scan error must retain the last valid catalogue');
  assert.match(state[2], /temporary scan failure/);
  assert.equal(requests.length, 3, 'One queued reload follows the failed request');
  const restored = [{ id: 'kept.desktop', name: 'Restored' }];
  requests[2].resolve(restored); await flush();
  assert.equal(state[0], restored); assert.equal(state[2], null);
  receive(); assert.equal(requests.length, 4);
  dispose(); const prior = [...state];
  requests[3].resolve([]); await flush(); receive(); await flush();
  assert.deepEqual(state, prior, 'Late completion cannot erase the snapshot after disposal');
  assert.equal(stopped, 1); assert.equal(requests.length, 4);
  assert.ok(calls.every(call => call.command === 'get_installed_apps'), 'Catalogue refresh cannot remove/change configuration pins');
  delete globalThis.__installedAppsTest;
});
