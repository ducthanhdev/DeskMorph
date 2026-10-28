import { readdir } from 'node:fs/promises';
for (const file of (await readdir(new URL('.', import.meta.url))).filter(f => f.endsWith('.test.mjs')).sort()) {
  await import(new URL(file, import.meta.url));
}
