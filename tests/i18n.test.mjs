import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/i18n/messages.ts', import.meta.url), 'utf8').replace('import resources from "./messages.json";', 'const resources = ' + fs.readFileSync(new URL('../src/i18n/messages.json', import.meta.url), 'utf8') + ';'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { messages, formatCount } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
test('Vietnamese and English cover the same UI messages', () => {
  assert.deepEqual(Object.keys(messages.vi).sort(), Object.keys(messages.en).sort());
  for (const language of Object.values(messages)) assert.ok(Object.values(language).every(value => value.trim().length));
});
test('window and application counts use locale and plural forms', () => {
  assert.equal(formatCount('en', 'window', 1), '1 window');
  assert.equal(formatCount('en', 'window', 2), '2 windows');
  assert.equal(formatCount('en', 'app', 0), '0 applications');
  assert.equal(formatCount('vi', 'window', 1), '1 cửa sổ');
  assert.equal(formatCount('vi', 'app', 2), '2 ứng dụng');
  assert.equal(formatCount('en', 'window', 1000), '1,000 windows');
  assert.equal(formatCount('vi', 'window', 1000), '1.000 cửa sổ');
});

const errorsSource = ts.transpileModule(fs.readFileSync(new URL('../src/i18n/errors.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText.replace('"./messages"', JSON.stringify('data:text/javascript;base64,' + Buffer.from(source).toString('base64')));
const { describeError } = await import('data:text/javascript;base64,' + Buffer.from(errorsSource).toString('base64'));
test('errors translate at display time, retain native codes and never expose raw diagnostics as the action message', () => {
  const raw = 'Unable to write /private/path [config_write; patch_config]';
  assert.deepEqual(describeError('en', raw), { summary: messages.en.configWriteError, code: 'config_write' });
  assert.deepEqual(describeError('vi', raw), { summary: messages.vi.configWriteError, code: 'config_write' });
  assert.equal(describeError('en', messages.vi.absoluteFolder).summary, messages.en.absoluteFolder);
  assert.equal(describeError('vi', messages.en.wallpaperError).summary, messages.vi.wallpaperError);
  assert.equal(describeError('en', 'config_conflict: native diagnostic').summary, messages.en.configConflict);
  assert.equal(describeError('vi', 'xprop_unavailable').summary, messages.vi.xpropMissing);
  assert.equal(describeError('en', 'Error: future_error: sensitive diagnostic').summary, messages.en.operationFailed);
  assert.equal(describeError('en', 'Error: future_error: sensitive diagnostic').code, 'future_error');
  assert.equal(describeError('vi', 'arbitrary backend failure').summary, messages.vi.operationFailed);
  assert.equal(describeError('en', 'future diagnostic [future_window_error; activate_window]').summary, messages.en.activateWindowError);
});

test('diagnostic disclosure follows keyboard button semantics and translates a retained error after language switch', async () => {
  let language = 'vi', expanded = false;
  globalThis.__errorTextTest = {
    useState: () => [expanded, value => { expanded = value(expanded); }],
    useI18n: () => ({ language, t: key => messages[language][key] }),
  };
  const jsxSource = 'export const jsx=(type,props)=>({type,props});export const jsxs=jsx;export const Fragment="Fragment";';
  const jsxUrl = 'data:text/javascript;base64,' + Buffer.from(jsxSource).toString('base64');
  let component = fs.readFileSync(new URL('../src/components/ErrorText.tsx', import.meta.url), 'utf8')
    .replace(/import \{ useState \} from .*;/, 'const { useState } = globalThis.__errorTextTest;')
    .replace(/import \{ useI18n \} from .*;/, 'const { useI18n } = globalThis.__errorTextTest;')
    .replace('"../i18n/errors"', JSON.stringify('data:text/javascript;base64,' + Buffer.from(errorsSource).toString('base64')));
  component = ts.transpileModule(component, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsxUrl));
  const { ErrorText } = await import('data:text/javascript;base64,' + Buffer.from(component).toString('base64'));
  function* nodes(value) {
    if (!value || typeof value !== 'object') return;
    yield value;
    for (const child of [value.props?.children].flat(Infinity)) yield* nodes(child);
  }
  const raw = 'private path diagnostic [config_write; patch_config]';
  try {
    let tree = ErrorText({ error: raw });
    assert.equal(tree.props.children[0], messages.vi.configWriteError);
    let button = [...nodes(tree)].find(node => node.type === 'button');
    assert.equal(button.props.type, 'button'); assert.equal(button.props['aria-expanded'], false);
    assert.equal([...nodes(tree)].some(node => node.props?.className === 'error-diagnostics'), false);
    button.props.onClick(); language = 'en'; tree = ErrorText({ error: raw });
    assert.equal(tree.props.children[0], messages.en.configWriteError);
    assert.equal([...nodes(tree)].find(node => node.type === 'button').props.children, messages.en.details);
    assert.equal([...nodes(tree)].find(node => node.props?.className === 'error-diagnostics').props.children, raw);
  } finally { delete globalThis.__errorTextTest; }
});

test('configuration warnings translate stable codes and legacy persisted text without treating a committed save as a failure', () => {
  for (const language of ['vi', 'en']) {
    for (const [code, key] of [ ['config_repaired', 'configRepaired'], ['config_recovered', 'configRecovered'],
      ['config_legacy_repaired', 'configLegacyRepaired'], ['config_legacy_unreadable', 'configLegacyUnreadable'],
      ['config_durability: directory sync failure', 'configDurability'] ]) {
      assert.equal(describeError(language, code).summary, messages[language][key]);
      assert.equal(describeError(language, messages.vi[key]).summary, messages[language][key]);
    }
    const legacy = messages.vi.configDurability.replace(/\.$/, '') + ': original OS detail';
    assert.equal(describeError(language, legacy).summary, messages[language].configDurability);
    assert.equal(describeError(language, 'future warning', 'configWarningUnknown').summary, messages[language].configWarningUnknown);
  }
});

const fieldsSource = ts.transpileModule(fs.readFileSync(new URL('../src/i18n/configFields.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText.replace('"./messages"', JSON.stringify('data:text/javascript;base64,' + Buffer.from(source).toString('base64')));
const { configFieldLabels, configFieldLabel, configReviewValue } = await import('data:text/javascript;base64,' + Buffer.from(fieldsSource).toString('base64'));
test('import review covers every config field and translates scalar values while preserving user data', () => {
  const defaults = JSON.parse(fs.readFileSync(new URL('../src/config/defaults.json', import.meta.url)));
  assert.deepEqual(Object.keys(configFieldLabels).sort(), Object.keys(defaults).sort());
  for (const language of ['vi', 'en']) {
    for (const field of Object.keys(defaults)) assert.ok(configFieldLabel(language, field));
    assert.equal(configReviewValue(language, 'enabled', true), messages[language].on);
    assert.equal(configReviewValue(language, 'enabled', false), messages[language].off);
    assert.equal(configReviewValue(language, 'monitor', null), messages[language].notSet);
    assert.equal(configReviewValue(language, 'position', 'bottom'), messages[language].bottom);
    assert.equal(configReviewValue(language, 'language', 'en'), 'English');
    assert.equal(configReviewValue(language, 'wallpaperFolders', ['/tmp/User_Name']), '[\n  "/tmp/User_Name"\n]');
    assert.equal(configFieldLabel(language, '__proto__'), '__proto__');
    assert.equal(configFieldLabel(language, 'futureField'), 'futureField');
  }
});

const pinSource = ts.transpileModule(fs.readFileSync(new URL('../src/i18n/pinNames.ts', import.meta.url), 'utf8')
  .replace('import defaults from "../config/defaults.json";', 'const defaults = ' + fs.readFileSync(new URL('../src/config/defaults.json', import.meta.url), 'utf8') + ';'),
  { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
  .replace('"./messages"', JSON.stringify('data:text/javascript;base64,' + Buffer.from(source).toString('base64')));
const { displayPinName } = await import('data:text/javascript;base64,' + Buffer.from(pinSource).toString('base64'));
test('bundled Files/Settings names translate for display while custom identities/names/commands remain user data', () => {
  const defaults = JSON.parse(fs.readFileSync(new URL('../src/config/defaults.json', import.meta.url)));
  const pin = defaults.pinnedApps.find(pin => pin.id === 'files');
  assert.equal(displayPinName('en', pin), 'Files');
  assert.equal(displayPinName('vi', pin), pin.name);
  for (const change of [{ name: 'My Documents' }, { command: 'custom-file-manager' }, { desktopId: 'files.desktop' }, { id: 'custom-files' }, { iconType: 'custom' }]) {
    const custom = { ...pin, ...change };
    assert.equal(displayPinName('en', custom), custom.name);
  }
  assert.equal(pin.name, 'Tệp tin (Files)');
});

test('stored success status follows language changes while paths and application names pass through', async () => {
  const { translateStoredText } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
  assert.equal(translateStoredText('en', messages.vi.configSaved), messages.en.configSaved);
  assert.equal(translateStoredText('vi', messages.en.wallpaperApplied), messages.vi.wallpaperApplied);
  assert.equal(translateStoredText('en', '/tmp/Tên-của-tôi.json'), '/tmp/Tên-của-tôi.json');
});
