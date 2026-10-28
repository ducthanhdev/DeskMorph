import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/hooks/asyncLifetime.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { AsyncLifetime, completePopupAction } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('StrictMode replacement invalidates old consumers without cancelling the new lifetime', async () => {
  const lifetime = new AsyncLifetime();
  lifetime.start(); const old = lifetime.capture();
  const launched = deferred(); let closes = 0;
  const result = completePopupAction(() => launched.promise, async () => { closes++; return true; }, old);
  lifetime.stop(); lifetime.start(); const current = lifetime.capture();
  launched.resolve(true);
  assert.equal(await result, false); assert.equal(closes, 0);
  assert.equal(old.aborted, true); assert.equal(current.aborted, false);
  assert.equal(await completePopupAction(async () => true, async () => { closes++; return true; }, current), true);
  assert.equal(closes, 1); lifetime.stop();
});

test('a delayed launch cannot dismiss a replacement generation; false results keep the popup open', async () => {
  const lifetime = new AsyncLifetime();
  const launched = deferred(); let activeGeneration = 10;
  const closeOpeningGeneration = async () => {
    if (activeGeneration !== 10) return false;
    activeGeneration = null; return true;
  };
  const result = completePopupAction(() => launched.promise, closeOpeningGeneration, lifetime.capture());
  activeGeneration = 11; launched.resolve(true);
  assert.equal(await result, false); assert.equal(activeGeneration, 11);
  let closes = 0;
  assert.equal(await completePopupAction(async () => false, async () => { closes++; return true; }, lifetime.capture()), false);
  assert.equal(closes, 0); lifetime.stop();
});

test('cleanup cancels queued focus frames and stale completions cannot schedule more frames', () => {
  let next = 0; const callbacks = new Map(); const cancelled = [];
  const lifetime = new AsyncLifetime(cb => { callbacks.set(++next, cb); return next; }, id => { cancelled.push(id); callbacks.delete(id); });
  const old = lifetime.capture(); let focused = 0;
  lifetime.frame(old, () => focused++);
  lifetime.stop(); assert.deepEqual(cancelled, [1]); assert.equal(callbacks.size, 0);
  lifetime.frame(old, () => focused++); assert.equal(next, 1);
  lifetime.start(); const current = lifetime.capture(); lifetime.frame(current, () => focused++);
  callbacks.get(2)(0); assert.equal(focused, 1);
  lifetime.stop(); assert.deepEqual(cancelled, [1]);
});


test('a disposed consumer cannot dispatch a new popup command', async () => {
  const lifetime = new AsyncLifetime(); const signal = lifetime.capture(); lifetime.stop();
  let dispatched = 0;
  assert.equal(await completePopupAction(async () => { dispatched++; return true; }, async () => { dispatched++; return true; }, signal), false);
  assert.equal(dispatched, 0);
});
