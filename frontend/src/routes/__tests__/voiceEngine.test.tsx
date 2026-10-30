import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import type { VoiceEngineStatus } from "@/hooks/useVoiceEngine"
import { libraryConfig } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import {
  serveSettingsSaving,
  settingsHandler,
  settingsOverview,
} from "@/test/mocks/settings"
import { renderAppAt } from "@/test/renderApp"

function section() {
  return screen.getByRole("region", { name: "Voice" })
}

async function openSettings() {
  const user = userEvent.setup()
  renderAppAt("/settings")
  await screen.findByRole("radio", { name: /Kokoro/ })
  return user
}

function countChecks(result: VoiceEngineStatus) {
  const calls = { count: 0 }
  server.use(
    http.post("/api/voices/check", () => {
      calls.count += 1
      return HttpResponse.json(result)
    }),
  )
  return calls
}

describe("voice engine settings", () => {
  it("shows the selected engine's fields and saves the switch", async () => {
    const patches: unknown[] = []
    server.use(...serveSettingsSaving(patches))
    const user = await openSettings()
    expect(screen.getByRole("radio", { name: /Kokoro/ })).toBeChecked()
    expect(screen.queryByLabelText("Speech model")).not.toBeInTheDocument()

    await user.click(
      screen.getByRole("radio", { name: /OpenAI-compatible speech/ }),
    )
    expect(screen.getByLabelText("Speech server address")).toHaveValue(
      "https://api.openai.com/v1",
    )
    expect(screen.getByLabelText("Speech server API key")).toHaveAttribute(
      "type",
      "password",
    )
    expect(
      screen.queryByLabelText("ElevenLabs API key"),
    ).not.toBeInTheDocument()
    const model = screen.getByLabelText("Speech model")
    await user.clear(model)
    await user.type(model, "kokoro-82m")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await within(section()).findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([
      { voice_engine: "openai_speech", openai_speech_model: "kokoro-82m" },
    ])
    expect(
      screen.getByRole("radio", { name: /OpenAI-compatible speech/ }),
    ).toBeChecked()
  })

  it("asks for an ElevenLabs key before saving", async () => {
    const patches: unknown[] = []
    server.use(...serveSettingsSaving(patches))
    const user = await openSettings()

    await user.click(screen.getByRole("radio", { name: /ElevenLabs/ }))
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(
      await within(section()).findByText("Error: Enter an API key."),
    ).toBeInTheDocument()
    expect(patches).toEqual([])
  })

  it("tests only on a click and shows a failing engine's hint", async () => {
    server.use(
      settingsHandler(
        settingsOverview({
          values: {
            voice_engine: {
              value: "elevenlabs",
              source: "saved",
              is_locked: false,
            },
          },
          secrets: {
            elevenlabs_api_key: {
              has_key: true,
              source: "saved",
              is_locked: false,
            },
          },
        }),
      ),
    )
    const checks = countChecks({
      is_ready: false,
      message: "ElevenLabs returned 401.",
      hint: "Check the API key in Settings.",
    })
    const user = await openSettings()
    expect(checks.count).toBe(0)

    await user.click(screen.getByRole("button", { name: "Test voice engine" }))

    expect(
      await screen.findByText("Test failed: ElevenLabs returned 401."),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Check the API key in Settings."),
    ).toBeInTheDocument()
    expect(checks.count).toBe(1)
  })

  it("disables M4A and MP3 when ffmpeg is missing", async () => {
    await openSettings()

    expect(screen.getByRole("option", { name: /WAV/ })).toBeEnabled()
    expect(screen.getByRole("option", { name: /M4A/ })).toBeDisabled()
    expect(screen.getByRole("option", { name: /MP3/ })).toBeDisabled()
    expect(screen.getByText(/ffmpeg is not installed/)).toBeInTheDocument()
  })

  it("saves M4A when ffmpeg is installed", async () => {
    const patches: unknown[] = []
    server.use(
      ...serveSettingsSaving(patches),
      http.get("/api/config", () =>
        HttpResponse.json({
          ...libraryConfig,
          ffmpeg: {
            is_present: true,
            version: "7.1",
            status: "ok",
            message: "ffmpeg 7.1 is installed.",
          },
        }),
      ),
    )
    const user = await openSettings()
    const format = screen.getByLabelText("Audio format")
    await within(format).findByRole("option", { name: /M4A/ })
    await expect
      .poll(() => within(format).getByRole("option", { name: /M4A/ }))
      .toBeEnabled()

    await user.selectOptions(format, "m4a")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await within(section()).findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([{ output_format: "m4a" }])
  })
})
