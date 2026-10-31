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

const saved = (value: string) =>
  ({ value, source: "saved", is_locked: false }) as const

const speechWithKey = {
  values: { voice_engine: saved("openai_speech") },
  secrets: {
    openai_speech_api_key: {
      has_key: true,
      source: "saved",
      is_locked: false,
    },
  },
} as const

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

  it("rejects an address that is not http or https and sends nothing", async () => {
    const patches: unknown[] = []
    server.use(...serveSettingsSaving(patches))
    const user = await openSettings()

    await user.click(
      screen.getByRole("radio", { name: /OpenAI-compatible speech/ }),
    )
    const address = screen.getByLabelText("Speech server address")
    await user.clear(address)
    await user.type(address, "ftp://x")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(
      await within(section()).findByText(
        "Error: Enter an address starting with http:// or https://.",
      ),
    ).toBeInTheDocument()
    expect(patches).toEqual([])
  })

  it("keeps a locked engine in place and still saves the other fields", async () => {
    const patches: unknown[] = []
    server.use(
      ...serveSettingsSaving(patches, {
        values: {
          voice_engine: {
            value: "openai_speech",
            source: "env",
            is_locked: true,
          },
        },
      }),
    )
    const user = await openSettings()

    expect(screen.getByRole("radio", { name: /Kokoro/ })).toBeDisabled()
    expect(screen.getByText(/engine is set by PHEMIUS_TTS/)).toBeInTheDocument()
    const model = screen.getByLabelText("Speech model")
    await user.clear(model)
    await user.type(model, "tts-1-hd")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await within(section()).findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([{ openai_speech_model: "tts-1-hd" }])
  })

  it("warns that a saved key follows a changed address", async () => {
    server.use(settingsHandler(settingsOverview(speechWithKey)))
    const user = await openSettings()
    expect(screen.queryByText(/saved key will be sent/)).not.toBeInTheDocument()

    const address = screen.getByLabelText("Speech server address")
    await user.clear(address)
    await user.type(address, "https://speech.example/v1")

    expect(
      within(section()).getByText(/saved key will be sent/),
    ).toBeInTheDocument()
  })

  it("does not send a key typed for an engine that is not selected", async () => {
    const patches: unknown[] = []
    server.use(...serveSettingsSaving(patches))
    const user = await openSettings()

    await user.click(screen.getByRole("radio", { name: /ElevenLabs/ }))
    await user.type(screen.getByLabelText("ElevenLabs API key"), "xi-secret")
    await user.click(
      screen.getByRole("radio", { name: /OpenAI-compatible speech/ }),
    )
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await within(section()).findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([{ voice_engine: "openai_speech" }])
  })

  it("saves an unsaved change before testing", async () => {
    const requests: unknown[] = []
    server.use(
      ...serveSettingsSaving(requests),
      http.post("/api/voices/check", () => {
        requests.push("check")
        return HttpResponse.json({ is_ready: true, message: "Piper is ready." })
      }),
    )
    const user = await openSettings()

    await user.click(screen.getByRole("radio", { name: /Piper/ }))
    await user.click(screen.getByRole("button", { name: "Test voice engine" }))

    expect(await screen.findByText("OK: Piper is ready.")).toBeInTheDocument()
    expect(requests).toEqual([{ voice_engine: "piper" }, "check"])
  })

  it("does not test when saving the change fails", async () => {
    const checks = countChecks({ is_ready: true, message: "Piper is ready." })
    server.use(
      http.patch("/api/settings", () =>
        HttpResponse.json(
          { detail: "The settings could not be saved.", code: "internal" },
          { status: 500 },
        ),
      ),
    )
    const user = await openSettings()

    await user.click(screen.getByRole("radio", { name: /Piper/ }))
    await user.click(screen.getByRole("button", { name: "Test voice engine" }))

    expect(
      await within(section()).findByText(
        "Not saved: The settings could not be saved.",
      ),
    ).toBeInTheDocument()
    expect(checks.count).toBe(0)
  })

  it("does not reload the config after a test", async () => {
    let configReads = 0
    server.use(
      http.get("/api/config", () => {
        configReads += 1
        return HttpResponse.json(libraryConfig)
      }),
    )
    countChecks({ is_ready: true, message: "Kokoro is ready." })
    const user = await openSettings()
    await screen.findByText(/ffmpeg is not installed/)
    const readsBeforeTest = configReads

    await user.click(screen.getByRole("button", { name: "Test voice engine" }))

    expect(await screen.findByText("OK: Kokoro is ready.")).toBeInTheDocument()
    expect(configReads).toBe(readsBeforeTest)
  })

  it("says why M4A and MP3 are off when ffmpeg could not be checked", async () => {
    server.use(
      http.get("/api/config", () =>
        HttpResponse.json(
          { detail: "Server error.", code: "internal" },
          { status: 500 },
        ),
      ),
    )
    await openSettings()

    expect(
      await screen.findByText(/Could not check for ffmpeg/),
    ).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /MP3/ })).toBeDisabled()
  })

  it("says when the saved engine is not one of the choices", async () => {
    server.use(
      settingsHandler(
        settingsOverview({ values: { voice_engine: saved("stub") } }),
      ),
    )
    await openSettings()

    expect(
      screen.getByText(/The saved engine, stub, is not one of these/),
    ).toBeInTheDocument()
  })
})
