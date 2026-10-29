import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

test('focused removals choose same-index/previous/fallback and never steal focus after async work', async () => {
  const refs = []; let slot = 0, effect;
  globalThis.__removalFocusTest = {
    useRef: initial => refs[slot++] ||= { current: initial },
    useLayoutEffect: callback => { effect = callback; },
  };
  const source = fs.readFileSync(new URL('../src/hooks/useRemovalFocus.ts', import.meta.url), 'utf8')
    .replace(/import .* from "react";/, 'const {useRef,useLayoutEffect}=globalThis.__removalFocusTest;');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const { useRemovalFocus } = await import('data:text/javascript;base64,' + Buffer.from(output).toString('base64'));
  const body = {}; let focus = null;
  globalThis.document = { body, activeElement: body };
  const button = name => ({ name, isConnected: true, focus() { focus = name; document.activeElement = this; } });
  let buttons = [button('first'), button('second'), button('third')];
  const render = () => { slot = 0; return useRemovalFocus(); };
  let hook = render(); hook.root.current = { isConnected: true, querySelectorAll: () => buttons };
  hook.fallback.current = button('search');
  try {
    hook.onFocusCapture({ target: buttons[1] }); const second = buttons[1];
    buttons.splice(1, 1); second.isConnected = false; render(); effect();
    assert.equal(focus, 'third');
    hook.onFocusCapture({ target: buttons[1] }); const third = buttons.pop();
    third.isConnected = false; document.activeElement = body; render(); effect();
    assert.equal(focus, 'first');
    hook.onFocusCapture({ target: buttons[0] }); const first = buttons.pop();
    first.isConnected = false; document.activeElement = body; render(); effect();
    assert.equal(focus, 'search');
    buttons = [button('async remove')]; hook.onFocusCapture({ target: buttons[0] });
    buttons[0].isConnected = false; buttons = []; document.activeElement = button('another control');
    focus = null; render(); effect(); assert.equal(focus, null);
    // Ordinary render/reorder must leave the connected focused control alone.
    buttons = [button('connected')]; hook.onFocusCapture({ target: buttons[0] });
    document.activeElement = body; render(); effect(); assert.equal(focus, null);
    // Focus moved within the settings before a completion: forget deletion origin.
    hook.onFocusCapture({ target: hook.fallback.current }); buttons[0].isConnected = false;
    buttons = []; render(); effect(); assert.equal(focus, null);
  } finally { delete globalThis.document; delete globalThis.__removalFocusTest; }
});
