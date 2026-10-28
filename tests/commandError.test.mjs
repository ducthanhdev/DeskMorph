import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString('base64');
const errorUrl = compile(fs.readFileSync(new URL('../src/commandError.ts', import.meta.url), 'utf8'));
const { CommandError, normalizeCommandError, errorMessage } = await import(errorUrl);

test('command errors normalize legacy codes, native objects, JS errors and invalid payloads without losing operation context', () => {
  const missing = normalizeCommandError('launch_app', 'app_missing: Đã gỡ ứng dụng');
  assert.equal(missing.code, 'app_missing'); assert.equal(missing.message, 'Đã gỡ ứng dụng');
  assert.equal(missing.command, 'launch_app'); assert.match(errorMessage(missing), /app_missing; launch_app/);
  assert.equal(normalizeCommandError('open_system_location', 'downloads_missing').code, 'downloads_missing');
  const saved = normalizeCommandError('patch_config', { code: 'window_show', message: 'Saved, apply failed', context: { persisted: true, revision: 8 } });
  assert.deepEqual(saved.context, { persisted: true, revision: 8 });
  assert.equal(normalizeCommandError('patch_config', saved), saved);
  assert.equal(normalizeCommandError('set_wallpaper', new Error('File disappeared')).message, 'File disappeared');
  assert.equal(normalizeCommandError('set_wallpaper', null).code, 'set_wallpaper_failed');
  assert.equal(errorMessage({ message: 'native failure' }), 'native failure');
  assert.deepEqual(normalizeCommandError('x', { context: 'invalid' }).context, {});
});

test('configuration retry resends failed saves, retains errors across events, and only reapplies already saved changes', async () => {
  let receive; let subscribed = false; const calls = [];
  let failure = null; let revision = 1;
  const snapshot = () => ({ config: { enabled: true }, revision, warning: null, schemaVersion: 1 });
  globalThis.__configErrorTest = {
    invoke: async (command, args) => { calls.push({ command, args }); if (failure) throw failure; return snapshot(); },
    listen: async (_event, callback) => { receive = callback; return () => {}; },
    useSyncExternalStore: (subscribe, get) => { if (!subscribed) { subscribed = true; subscribe(() => {}); } return get(); },
  };
  let source = fs.readFileSync(new URL('../src/config/store.ts', import.meta.url), 'utf8');
  source = source.replace(/import \{ invoke \} from .*;/, 'const { invoke } = globalThis.__configErrorTest;')
    .replace(/import \{ listen \} from .*;/, 'const { listen } = globalThis.__configErrorTest;')
    .replace(/import \{ useSyncExternalStore \} from .*;/, 'const { useSyncExternalStore } = globalThis.__configErrorTest;')
    .replace(/import \{ DEFAULT_CONFIG,.*;/, 'const DEFAULT_CONFIG = {};')
    .replaceAll('"../commandError"', JSON.stringify(errorUrl));
  const store = await import(compile(source));
  store.useConfig(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(store.useConfig().ready, true);
  failure = new CommandError('config_write', 'No permission', 'patch_config');
  assert.equal(await store.useConfig().updateConfig({ enabled: false }), false);
  assert.equal(store.useConfig().config.enabled, true);
  receive({ payload: snapshot() }); assert.match(store.useConfig().error, /No permission/);
  failure = null; store.useConfig().retry(); store.useConfig().retry(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.filter(c => c.command === 'patch_config').length, 2);
  assert.equal(calls.at(-1).command, 'patch_config'); assert.deepEqual(calls.at(-1).args.patch, { enabled: false });
  assert.equal(calls.at(-1).args.expectedRevision, 1);
  assert.equal(store.useConfig().error, null);
  failure = new CommandError('window_show', 'Saved but window failed', 'mutate_pin', { persisted: true, revision: ++revision });
  assert.equal(await store.mutatePin('toggleEnabled', 'pin'), false);
  receive({ payload: snapshot() }); assert.match(store.useConfig().error, /Saved but window failed/);
  failure = null; store.useConfig().retry(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.at(-1).command, 'retry_config_apply'); assert.equal(calls.filter(c => c.command === 'mutate_pin').length, 1);
  assert.equal(store.useConfig().error, null);
  failure = new CommandError('config_write', 'Import write failed', 'replace_config_document');
  await store.replaceConfigDocument({ schemaVersion: 1, config: {} }, 1);
  failure = new CommandError('config_conflict', 'Stale review', 'replace_config_document');
  store.useConfig().retry(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.at(-1).args.expectedRevision, 1); assert.match(store.useConfig().error, /Stale review/);
  delete globalThis.__configErrorTest;
});
