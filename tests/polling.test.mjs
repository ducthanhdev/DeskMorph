import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/hooks/polling.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { startPolling } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
class Visibility extends EventTarget {
  hidden = false;
  change(hidden) { this.hidden = hidden; this.dispatchEvent(new Event('visibilitychange')); }
}

test('visibility changes during a pending request retain one timer and never overlap', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const visibility = new Visibility();
  const pending = deferred();
  let calls = 0;
  const stop = startPolling(() => async () => { calls++; if (calls === 1) await pending.promise; }, 1000, { current: null }, visibility);
  t.after(stop);
  await flush();
  for (let i = 0; i < 5; i++) { visibility.change(true); visibility.change(false); }
  t.mock.timers.tick(5000);
  await flush();
  assert.equal(calls, 1);
  pending.resolve(); await flush();
  t.mock.timers.tick(999); await flush(); assert.equal(calls, 1);
  t.mock.timers.tick(1); await flush(); assert.equal(calls, 2);
  t.mock.timers.tick(999); await flush(); assert.equal(calls, 2);
  t.mock.timers.tick(1); await flush(); assert.equal(calls, 3);
  stop(); t.mock.timers.tick(5000); await flush(); assert.equal(calls, 3);
});

test('StrictMode replacement waits for native IPC, aborts stale consumers and uses latest task', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const visibility = new Visibility();
  const slot = { current: null };
  const pending = deferred();
  let oldSignal;
  let oldCalls = 0;
  let newCalls = 0;
  const stopOld = startPolling(() => async signal => { oldCalls++; oldSignal = signal; await pending.promise; }, 100, slot, visibility);
  await flush(); stopOld();
  let task = async () => { newCalls++; };
  const stopNew = startPolling(() => task, 1000, slot, visibility);
  t.after(stopNew);
  t.mock.timers.tick(5000); await flush();
  assert.equal(oldSignal.aborted, true);
  assert.equal(oldCalls, 1); assert.equal(newCalls, 0);
  pending.resolve(); await flush(); assert.equal(newCalls, 1);
  task = async () => { newCalls += 10; };
  t.mock.timers.tick(1000); await flush(); assert.equal(newCalls, 11);
  stopNew(); assert.equal(slot.current, null);
});

test('hidden windows sleep until visible and pending completions cannot restart stopped polling', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const visibility = new Visibility(); visibility.hidden = true;
  const pending = deferred();
  let calls = 0;
  const stop = startPolling(() => async () => { calls++; await pending.promise; }, 100, { current: null }, visibility);
  t.after(stop);
  t.mock.timers.tick(1000); await flush(); assert.equal(calls, 0);
  visibility.change(false); await flush(); assert.equal(calls, 1);
  visibility.change(true); pending.resolve(); await flush();
  t.mock.timers.tick(1000); await flush(); assert.equal(calls, 1);
  visibility.change(false); await flush(); assert.equal(calls, 2);
  stop(); visibility.change(false); t.mock.timers.tick(1000); await flush(); assert.equal(calls, 2);
});

test('request errors do not stop subsequent polls', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const logged = t.mock.method(console, 'error', () => {});
  let calls = 0;
  const stop = startPolling(() => async () => { if (++calls === 1) throw new Error('native unavailable'); }, 100, { current: null }, new Visibility());
  t.after(stop);
  await flush(); assert.equal(logged.mock.callCount(), 1);
  t.mock.timers.tick(100); await flush(); assert.equal(calls, 2);
});
