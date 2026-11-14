import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { server } from "@/test/mocks/server"
import { libraryConfig } from "@/test/mocks/handlers"
import {
  serveSettingsSaving,
  settingsHandler,
  settingsOverview,
} from "@/test/mocks/settings"
import { kokoroVoices, voicesHandler } from "@/test/mocks/voices"
import { renderAppAt } from "@/test/renderApp"

function voiceList() {
  return screen.getByRole("group", { name: "Default voice (Kokoro)" })
}

async function openSettings() {
  const user = userEvent.setup()
  renderAppAt("/settings")
  await screen.findByRole("radio", { name: /Heart/ })
  return user
}

// The list reflects the saved default, as the server does after a PATCH.
function serveDefaultVoice(patches: unknown[]) {
  const defaultVoice = () =>
    patches
      .map((patch) => (patch as { default_voice?: string }).default_voice)
      .filter(Boolean)
      .at(-1) ?? "kokoro:af_heart"
  server.use(
    ...serveSettingsSaving(patches),
    voicesHandler(() =>
      kokoroVoices.map((voice) => ({
        ...voice,
        is_default: voice.id === defaultVoice(),
      })),
    ),
  )
}

const savedStatus = (value: string) =>
  ({ value, source: "saved", is_locked: false }) as const

// Holds the first save until released; the list shows what was saved last.
function serveSlowFirstSave() {
  const arrived: unknown[] = []
  let saved = "kokoro:af_heart"
  let releaseFirst = () => {}
  const firstGate = new Promise<void>((resolve) => {
    releaseFirst = resolve
  })
  server.use(
    http.patch("/api/settings", async ({ request }) => {
      const patch = (await request.json()) as { default_voice: string }
      arrived.push(patch)
      if (arrived.length === 1) await firstGate
      saved = patch.default_voice
      return HttpResponse.json(
        settingsOverview({ values: { default_voice: savedStatus(saved) } }),
      )
    }),
    voicesHandler(() =>
      kokoroVoices.map((voice) => ({
        ...voice,
        is_default: voice.id === saved,
      })),
    ),
  )
  return { arrived, releaseFirst, saved: () => saved }
}

function countConfigReads() {
  const calls = { count: 0 }
  server.use(
    http.get("/api/config", () => {
      calls.count += 1
      return HttpResponse.json(libraryConfig)
    }),
  )
  return calls
}

describe("voice list", () => {
  it("lists each voice with its accent, licence and install state in text", async () => {
    await openSettings()
    const george = within(voiceList()).getByRole("radio", { name: /George/ })

    expect(george).toHaveAccessibleName(/British English, male/)
    expect(george).toHaveAccessibleName(/Not installed · 82\.0 MB/)
    expect(george).toHaveAccessibleName(/Licence: Apache-2\.0/)
    expect(
      within(voiceList()).getByRole("radio", { name: /Heart/ }),
    ).toHaveAccessibleName(/Default · Installed/)
    expect(
      within(voiceList()).getByRole("radio", { name: /Heart/ }),
    ).toBeChecked()
  })

  it("sets a default voice, updates the list and keeps it after a reload", async () => {
    const patches: unknown[] = []
    serveDefaultVoice(patches)
    const user = await openSettings()

    await user.click(within(voiceList()).getByRole("radio", { name: /Bella/ }))

    expect(
      await within(voiceList()).findByRole("radio", { name: /Bella.*Default/ }),
    ).toBeChecked()
    expect(
      within(voiceList()).getByRole("radio", { name: /Heart/ }),
    ).not.toBeChecked()
    expect(patches).toEqual([{ default_voice: "kokoro:af_bella" }])

    cleanup()
    await openSettings()
    expect(
      within(voiceList()).getByRole("radio", { name: /Bella/ }),
    ).toBeChecked()
  })

  it("shows why a default voice was not saved and keeps the old one", async () => {
    server.use(
      http.patch("/api/settings", () =>
        HttpResponse.json(
          {
            detail: "Some settings are not offered by this library.",
            code: "invalid_setting",
            errors: [
              { field: "default_voice", message: "Not a kokoro voice." },
            ],
          },
          { status: 422 },
        ),
      ),
    )
    const user = await openSettings()

    await user.click(within(voiceList()).getByRole("radio", { name: /Bella/ }))

    expect(
      await screen.findByText("Not saved: Not a kokoro voice."),
    ).toBeInTheDocument()
    expect(
      within(voiceList()).getByRole("radio", { name: /Heart/ }),
    ).toBeChecked()
  })

  it("saves the default tone and says when it applies", async () => {
    const patches: unknown[] = []
    server.use(...serveSettingsSaving(patches))
    const user = await openSettings()
    const tone = screen.getByLabelText("Default tone")

    expect(tone).toHaveValue("neutral")
    expect(tone).toHaveAccessibleDescription(
      /only when a document has no suggested tone/,
    )
    await user.selectOptions(tone, "teacher")

    expect(await screen.findByText("Default tone saved.")).toBeInTheDocument()
    expect(patches).toEqual([{ default_tone: "teacher" }])
  })

  it("shows a field error when the tone is not offered", async () => {
    server.use(
      http.patch("/api/settings", () =>
        HttpResponse.json(
          {
            detail: "Some settings are not offered by this library.",
            code: "invalid_setting",
            errors: [
              { field: "default_tone", message: "Choose one of: neutral." },
            ],
          },
          { status: 422 },
        ),
      ),
    )
    const user = await openSettings()

    await user.selectOptions(screen.getByLabelText("Default tone"), "teacher")

    expect(
      await screen.findByText("Error: Choose one of: neutral."),
    ).toBeInTheDocument()
    expect(screen.getByLabelText("Default tone")).toHaveValue("neutral")
  })

  it("saves once where quick picks stop, without rechecking the engine", async () => {
    const patches: unknown[] = []
    serveDefaultVoice(patches)
    const configReads = countConfigReads()
    const user = await openSettings()
    const readsAtLoad = configReads.count

    await user.click(within(voiceList()).getByRole("radio", { name: /Bella/ }))
    await user.click(within(voiceList()).getByRole("radio", { name: /George/ }))

    expect(
      within(voiceList()).getByRole("radio", { name: /George/ }),
    ).toBeChecked()
    expect(
      await within(voiceList()).findByRole("radio", {
        name: /George.*Default/,
      }),
    ).toBeChecked()
    expect(patches).toEqual([{ default_voice: "kokoro:bm_george" }])
    expect(configReads.count).toBe(readsAtLoad)
  })

  it("keeps the last pick when an earlier save is still running", async () => {
    const server = serveSlowFirstSave()
    const user = await openSettings()

    await user.click(within(voiceList()).getByRole("radio", { name: /Bella/ }))
    await waitFor(() => expect(server.arrived).toHaveLength(1))
    await user.click(within(voiceList()).getByRole("radio", { name: /George/ }))
    expect(
      within(voiceList()).getByRole("radio", { name: /George/ }),
    ).toBeChecked()

    server.releaseFirst()

    await waitFor(() => expect(server.saved()).toBe("kokoro:bm_george"))
    expect(
      await within(voiceList()).findByRole("radio", {
        name: /George.*Default/,
      }),
    ).toBeChecked()
    expect(server.arrived).toEqual([
      { default_voice: "kokoro:af_bella" },
      { default_voice: "kokoro:bm_george" },
    ])
  })

  it("locks the default voice when PHEMIUS_VOICE sets it", async () => {
    server.use(
      settingsHandler(
        settingsOverview({
          values: {
            default_voice: {
              value: "kokoro:af_heart",
              source: "env",
              is_locked: true,
            },
          },
        }),
      ),
    )
    await openSettings()

    expect(
      within(voiceList()).getByText(/set by PHEMIUS_VOICE on the server/),
    ).toBeInTheDocument()
    for (const radio of within(voiceList()).getAllByRole("radio"))
      expect(radio).toBeDisabled()
  })
})
