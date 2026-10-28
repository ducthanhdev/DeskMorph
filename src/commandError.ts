/** Public UI error contract. Context contains operation metadata, never invoke arguments. */
export class CommandError extends Error {
  constructor(readonly code: string, message: string, readonly command: string, readonly context: Record<string, unknown> = {}) {
    super(message); this.name = "CommandError";
  }
  toString() { return `${this.message} [${this.code}; ${this.command}]`; }
}
export function normalizeCommandError(command: string, failure: unknown): CommandError {
  if (failure instanceof CommandError && failure.command === command) return failure;
  const value = failure && typeof failure === "object" ? failure as Record<string, unknown> : null;
  const raw = value && typeof value.message === "string" ? value.message : typeof failure === "string" ? failure : "Command failed";
  const legacy = /^([a-z][a-z0-9_]+)(?::\s*(.*))?$/s.exec(raw);
  const code = value && typeof value.code === "string" ? value.code : legacy?.[1] || `${command}_failed`;
  const message = legacy?.[2] || raw;
  const context = value?.context && typeof value.context === "object" && !Array.isArray(value.context) ? value.context as Record<string, unknown> : {};
  return new CommandError(code, message, command, context);
}
export function errorMessage(error: unknown): string {
  if (error instanceof CommandError) return error.toString();
  if (error && typeof error === "object" && "message" in error) return String(error.message);
  return String(error);
}
