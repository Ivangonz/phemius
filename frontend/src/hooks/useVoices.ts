import { useQuery } from "@tanstack/react-query"
import { api, withQuery } from "@/lib/api"
import type { components } from "@/lib/api-schema"
import { voicesQueryKey } from "./useSettings"

export type VoiceView = components["schemas"]["VoiceView"]
type VoicePage = components["schemas"]["Page_VoiceView_"]

// The API's largest page; engines offer a few dozen voices at most.
export const VOICE_PAGE_SIZE = 100

export function useVoices() {
  return useQuery({
    queryKey: voicesQueryKey,
    queryFn: () =>
      api.get<VoicePage>(
        withQuery("/voices", {
          order_by: "default",
          limit: VOICE_PAGE_SIZE,
          offset: 0,
        }),
      ),
  })
}
