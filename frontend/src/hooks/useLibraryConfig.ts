import { useQuery } from "@tanstack/react-query"
import { z } from "zod"
import { api } from "@/lib/api"
import type { paths } from "@/lib/api-schema"

type ConfigResponse =
  paths["/api/config"]["get"]["responses"][200]["content"]["application/json"]

// The endpoint has no response model yet, so its generated type is an open
// record; parse the fields the UI reads.
const libraryConfigSchema = z.object({
  llm: z.boolean(),
  model: z.string(),
  tts: z.string(),
  default_voice: z.string().nullable(),
})

export type LibraryConfig = z.infer<typeof libraryConfigSchema>

export const libraryConfigQueryKey = ["config"] as const

export function useLibraryConfig() {
  return useQuery({
    queryKey: libraryConfigQueryKey,
    queryFn: async () =>
      libraryConfigSchema.parse(await api.get<ConfigResponse>("/config")),
  })
}
