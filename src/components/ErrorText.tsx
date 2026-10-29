import { useState } from "react";
import { describeError } from "../i18n/errors";
import { useI18n } from "../i18n/useI18n";

/** A translated action message; original diagnostics remain available for support. */
export function ErrorText({ error, kind = "error" }: { error: string; kind?: "error" | "warning" }) {
  const { language, t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const { summary, code } = describeError(language, error, kind === "warning" ? "configWarningUnknown" : "operationFailed");
  const command = /\[[a-z][a-z0-9_]+;\s*([a-z][a-z0-9_]*)\]$/.exec(error)?.[1];
  return <span className="localized-error">{summary}{code && <small> ({code}{command && `; ${command}`})</small>}
    {summary !== error && <><button type="button" className="error-details-toggle" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{t("details")}</button>
      {expanded && <span className="error-diagnostics">{error}</span>}</>}
  </span>;
}
