import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/hooks/popupVisibility.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { watchPopupVisibility } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('late listener registration after StrictMode cleanup disconnects without querying or publishing', async () => {
  const registration = deferred();
  let receive, stopped = 0, queries = 0;
  const values = [];
  const stop = watchPopupVisibility(cb => { receive = cb; return registration.promise; }, async () => { queries++; return true; }, v => values.push(v), assert.fail);
  stop(); stop(); receive(true);
  registration.resolve(() => stopped++); await flush();
  assert.equal(stopped, 1); assert.equal(queries, 0); assert.deepEqual(values, []);
});

test('query observes a hide missed during registration; a newer hide beats an older query result', async () => {
  const registration = deferred(), query = deferred();
  let receive, queries = 0;
  const values = [];
  const stop = watchPopupVisibility(cb => { receive = cb; return registration.promise; }, () => { queries++; return query.promise; }, v => values.push(v), assert.fail);
  receive(true); // Opening event while registration is still resolving.
  registration.resolve(() => {}); await flush(); assert.equal(queries, 1);
  query.resolve(false); await flush(); assert.deepEqual(values, [true, false]);
  stop();
  const staleQuery = deferred(); const later = [];
  const stopLater = watchPopupVisibility(async cb => { receive = cb; return () => {}; }, () => staleQuery.promise, v => later.push(v), assert.fail);
  await flush(); receive(false); staleQuery.resolve(true); await flush();
  assert.deepEqual(later, [false]); stopLater();
});

test('pending query success/error after cleanup cannot update a replacement popup', async () => {
  const query = deferred(); let stopped = 0;
  const stop = watchPopupVisibility(async () => () => stopped++, () => query.promise, assert.fail, assert.fail);
  await flush(); stop(); query.resolve(true); await flush(); assert.equal(stopped, 1);
  let reject; const failed = new Promise((_, r) => { reject = r; });
  const stopFailed = watchPopupVisibility(async () => () => {}, () => failed, assert.fail, assert.fail);
  await flush(); stopFailed(); reject(new Error('late failure')); await flush();
});
