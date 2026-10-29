import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
test('focus within survives child transitions, clears on native blur and cancels stale mapping callbacks', async () => {
 let state=false,cleanup;const listeners=new Map(),frames=new Map();let id=0;
 const child={},other={};const root={current:{contains:node=>node===child}};
 globalThis.document={activeElement:child,hasFocus:()=>nativeFocus};let nativeFocus=true;
 globalThis.window={addEventListener:(name,handler)=>listeners.set(name,handler),removeEventListener:name=>listeners.delete(name)};
 globalThis.requestAnimationFrame=callback=>{frames.set(++id,callback);return id;};globalThis.cancelAnimationFrame=key=>frames.delete(key);
 globalThis.__focusWithin={useState:()=>[state,value=>{state=value;}],useEffect:callback=>{if(!cleanup)cleanup=callback();}};
 const source=fs.readFileSync(new URL('../src/hooks/useFocusWithin.ts',import.meta.url),'utf8').replace(/import .* from "react";/,'const {useState,useEffect}=globalThis.__focusWithin;');
 const output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
 const {useFocusWithin}=await import('data:text/javascript;base64,'+Buffer.from(output).toString('base64'));
 try{
  let hook=useFocusWithin(root);assert.equal(state,true);
  hook.onBlurCapture({currentTarget:root.current,relatedTarget:child});assert.equal(state,true);
  hook.onBlurCapture({currentTarget:root.current,relatedTarget:other});assert.equal(state,false);
  hook.onFocusCapture();assert.equal(state,true);
  nativeFocus=false;listeners.get('blur')();assert.equal(state,false);
  // DOM still names the old focused button while the native window is elsewhere.
  hook=useFocusWithin(root);assert.equal(hook.focused,false);
  listeners.get('focus')();assert.equal(state,false);assert.equal(frames.size,1);
  nativeFocus=true;for(const callback of frames.values())callback();frames.clear();assert.equal(state,true);
  document.activeElement=other;listeners.get('focus')();assert.equal(state,false);
  listeners.get('blur')();assert.equal(frames.size,0);
  document.activeElement=child;hook.onFocusCapture();assert.equal(state,true);
  listeners.get('focus')();cleanup();assert.equal(listeners.size,0);assert.equal(frames.size,0);
 }finally{for(const name of ['document','window','requestAnimationFrame','cancelAnimationFrame','__focusWithin'])delete globalThis[name];}
});
