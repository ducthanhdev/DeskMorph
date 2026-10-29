import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

test('popup focus survives pending disable, falls back after removal, and respects newer focus/native blur', async () => {
  const refs = []; let slot = 0, effect;
  globalThis.__popupFocus = {
    useRef: initial => refs[slot++] ||= { current: initial },
    useLayoutEffect: callback => { effect = callback; },
  };
  const source = fs.readFileSync(new URL('../src/hooks/usePopupFocus.ts', import.meta.url), 'utf8')
    .replace(/import .* from "react";/, 'const {useRef,useLayoutEffect}=globalThis.__popupFocus;');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const { usePopupFocus } = await import('data:text/javascript;base64,' + Buffer.from(output).toString('base64'));
  let nativeFocus = true;
  const body = {};
  globalThis.document = { body, activeElement: body, hasFocus: () => nativeFocus };
  const close = { focus() { document.activeElement = this; } };
  const root = { current: { closest: () => ({ querySelector: () => close }) } };
  const control = () => ({ isConnected: true, disabled: false, matches() { return this.disabled; }, closest: () => root.current, focus() { document.activeElement = this; } });
  let active = true, busy = false;
  const render = () => { slot = 0; return usePopupFocus(root, active, busy); };
  const seed = element => { document.activeElement = element; render().onFocusCapture({ target: element }); };
  const commit = () => { render(); effect(); };
  try {
    const play = control(); seed(play);
    busy = true; play.disabled = true; document.activeElement = body; commit();
    assert.equal(document.activeElement, body, 'Do not move focus during pending');
    busy = false; play.disabled = false; commit();
    assert.equal(document.activeElement, play, 'Restore same control after reenable/label change');
    const radio = control(); seed(radio); radio.isConnected = false; document.activeElement = body; commit();
    assert.equal(document.activeElement, close, 'Removed control goes to popup Close');
    const unsupported = control(); seed(unsupported); unsupported.disabled = true; document.activeElement = body; commit();
    assert.equal(document.activeElement, close, 'Newly unsupported control falls back');
    const failed = control(); seed(failed); busy = true; failed.disabled = true; document.activeElement = body; commit();
    const retry = control(); document.activeElement = retry;
    failed.disabled = false; busy = false; commit();
    assert.equal(document.activeElement, retry, 'Async completion must respect another control');
    seed(failed); busy = true; failed.disabled = true; document.activeElement = body; commit();
    nativeFocus = false; failed.disabled = false; busy = false; commit();
    assert.equal(document.activeElement, body, 'Native blur prevents focus restoration');
    nativeFocus = true; commit(); assert.equal(document.activeElement, body, 'Do not restore on a later unrelated render');
    seed(failed); const nested = control(); nested.closest = () => ({});
    render().onFocusCapture({ target: nested }); failed.isConnected = false; document.activeElement = body; commit();
    assert.equal(document.activeElement, body, 'Nested scope owns recovery');
    const hidden = control(); seed(hidden); hidden.isConnected = false; document.activeElement = body;
    active = false; commit(); active = true; commit();
    assert.equal(document.activeElement, body, 'Hidden generation cannot restore stale focus');
    const unchanged = control(); seed(unchanged); document.activeElement = body; commit();
    assert.equal(document.activeElement, body, 'Ordinary rerender does not seize focus');
  } finally { delete globalThis.document; delete globalThis.__popupFocus; }
});
