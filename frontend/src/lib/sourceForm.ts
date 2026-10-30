import { z } from "zod"
import type { components } from "./api-schema"
import { folderPath } from "./sourceDetails"

type SourceView = components["schemas"]["SourceView"]
type SourceChange = components["schemas"]["SourceChange"]
type NewSource = components["schemas"]["NewSourceRequest"]

// The server checks the folder exists and is allowed; this only catches typos.
export const sourceFormSchema = z.object({
  name: z.string().trim().max(200, "Use 200 characters or fewer."),
  path: z
    .string()
    .trim()
    .min(1, "Enter the folder's path.")
    .regex(
      /^(\/|~|[A-Za-z]:[\\/])/,
      "Use an absolute path, such as /home/me/docs or ~/docs.",
    ),
})

export type SourceFormValues = z.infer<typeof sourceFormSchema>

export const EMPTY_SOURCE_FORM: SourceFormValues = { name: "", path: "" }

export function toSourceFormValues(source: SourceView): SourceFormValues {
  return { name: source.name, path: folderPath(source) ?? "" }
}

export function toNewSource(values: SourceFormValues): NewSource {
  return {
    kind: "folder",
    config: { path: values.path },
    name: values.name || null,
  }
}

export function toSourceChange(
  values: SourceFormValues,
  source: SourceView,
): SourceChange {
  const saved = toSourceFormValues(source)
  const change: SourceChange = {}
  if (values.name && values.name !== saved.name) change.name = values.name
  if (!source.is_locked && values.path !== saved.path)
    change.config = { path: values.path }
  return change
}
