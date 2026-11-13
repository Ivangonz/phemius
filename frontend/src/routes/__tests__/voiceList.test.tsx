import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import { server } from "@/test/mocks/server"
import { serveSettingsSaving } from "@/test/mocks/settings"
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
})
