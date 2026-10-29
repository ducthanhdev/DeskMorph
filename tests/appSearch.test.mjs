import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/appSearch.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { searchApps, normalizeSearch, installedForPin, pinFromApp, desktopIdForPin, launchCommandForPin, desktopIsMissing } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const app = (id, name, extra = {}) => ({ id, name, genericName: '', keywords: [], matchClasses: [], executable: '/bin/true', iconPath: null, actions: [], ...extra });

test('Vietnamese search ignores accents, case and extra spaces', () => {
  assert.equal(normalizeSearch('  ĐỔI ẢNH  '), 'doi anh');
  const apps = [app('files.desktop', 'Tệp tin'), app('settings.desktop', 'Cài đặt', { keywords: ['cấu hình'] })];
  assert.deepEqual(searchApps(apps, 'TEP TIN').map(a => a.id), ['files.desktop']);
  assert.deepEqual(searchApps(apps, 'cau hinh').map(a => a.id), ['settings.desktop']);
});
test('search ranks exact, prefix, substring and keywords with deterministic ties', () => {
  const apps = [app('z.desktop', 'Other', { keywords: ['code'] }), app('b.desktop', 'Code Editor'), app('a.desktop', 'Code'), app('c.desktop', 'My Code')];
  assert.deepEqual(searchApps(apps, 'code').map(a => a.id), ['a.desktop', 'b.desktop', 'c.desktop', 'z.desktop']);
  assert.equal(searchApps(apps, 'missing').length, 0);
  assert.equal(searchApps(apps, '').length, 4);
});
test('desktop identity wins over legacy rules and pin creation preserves safe launcher identity', () => {
  const apps = [app('one.desktop', 'One', { executable: '/bin/editor', matchClasses: ['editor'] }), app('two.desktop', 'Two', { matchClasses: ['editor'] })];
  const pin = { id: 'legacy', command: 'editor', matchClasses: ['editor'] };
  assert.equal(installedForPin(pin, apps).id, 'one.desktop');
  assert.equal(installedForPin({ ...pin, desktopId: 'two.desktop' }, apps).id, 'two.desktop');
  assert.equal(installedForPin({ ...pin, desktopId: 'removed.desktop' }, apps), undefined);
  assert.equal(pinFromApp(apps[0]).command, 'desktop:one.desktop');
  assert.equal(pinFromApp(apps[0]).desktopId, 'one.desktop');
});

test('removed desktop identities and ambiguous legacy hints never resolve to another application', () => {
  const apps = [app('one.desktop', 'One', { executable: '/bin/editor', matchClasses: ['editor'] }), app('two.desktop', 'Two', { executable: '/opt/editor', matchClasses: ['editor'] })];
  const pin = { id: 'legacy', command: 'custom --profile work', matchClasses: ['EDITOR'] };
  assert.equal(installedForPin(pin, apps), undefined);
  assert.equal(installedForPin({ ...pin, command: 'editor' }, apps), undefined);
  assert.equal(installedForPin({ ...pin, command: '/opt/editor' }, apps)?.id, 'two.desktop');
  for (const command of ['desktop:removed.desktop', 'removed.desktop']) {
    assert.equal(installedForPin({ ...pin, command }, apps), undefined);
    assert.equal(desktopIdForPin({ ...pin, command }), 'removed.desktop');
  }
  assert.equal(installedForPin({ ...pin, command: 'one.desktop' }, apps)?.id, 'one.desktop');
});
test('legacy commands keep arguments while explicit desktop identity determines launch', () => {
  const pin = { id: 'legacy', command: '/opt/editor --profile "two words"', matchClasses: ['editor'] };
  const apps = [app('editor.desktop', 'Editor', { matchClasses: ['editor'] })];
  assert.equal(installedForPin(pin, apps)?.id, 'editor.desktop');
  assert.equal(launchCommandForPin(pin), pin.command);
  assert.equal(launchCommandForPin({ ...pin, desktopId: 'editor.desktop' }), 'desktop:editor.desktop');
  assert.equal(launchCommandForPin({ ...pin, command: 'editor.desktop' }), 'desktop:editor.desktop');
  assert.equal(launchCommandForPin(pinFromApp(apps[0])), 'desktop:editor.desktop');
});

test('only successful catalogue absence marks an explicit desktop pin missing; scan errors preserve its identity', () => {
  const pin = { id: 'custom', desktopId: 'removed.desktop', command: 'desktop:removed.desktop', matchClasses: ['editor'] };
  const original = JSON.stringify(pin);
  const id = desktopIdForPin(pin);
  assert.equal(desktopIsMissing(id, undefined, { loading: false, error: null }), true);
  assert.equal(desktopIsMissing(id, undefined, { loading: true, error: null }), false);
  assert.equal(desktopIsMissing(id, undefined, { loading: false, error: 'temporary scan failure' }), false);
  assert.equal(desktopIsMissing(id, app(id, 'Restored'), { loading: false, error: null }), false);
  assert.equal(desktopIsMissing(undefined, undefined, { loading: false, error: null }), false);
  assert.equal(JSON.stringify(pin), original);
  assert.equal(launchCommandForPin(pin), 'desktop:removed.desktop');
});
