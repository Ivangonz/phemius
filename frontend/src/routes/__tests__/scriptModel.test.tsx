import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"
import type { ScriptModelConnection } from "@/hooks/useScriptModels"
import { libraryConfig } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import {
  serveSettingsSaving,
  settingsHandler,
  settingsOverview,
} from "@/test/mocks/settings"
import { renderAppAt } from "@/test/renderApp"

const OLLAMA_MODELS = {
  models: [
    { name: "llama3.2:latest", size_bytes: 2_019_393_189 },
    { name: "qwen2.5:7b", size_bytes: 4_683_087_332 },
  ],
}

function section() {
  return screen.getByRole("region", { name: "Script model" })
}

async function openSettings() {
  const user = userEvent.setup()
  renderAppAt("/settings")
  await screen.findByRole("radio", { name: /OpenRouter/ })
  return user
}

function serveOllamaModels() {
  server.use(
    http.get("/api/models/ollama", () => HttpResponse.json(OLLAMA_MODELS)),
  )
}

function serveSaving(patches: unknown[]) {
  server.use(...serveSettingsSaving(patches))
}

function serveCheck(result: ScriptModelConnection) {
  server.use(http.post("/api/models/check", () => HttpResponse.json(result)))
}

describe("script model settings", () => {
  it("shows a saved key only as Key saved, with Replace", async () => {
    const user = await openSettings()

    expect(screen.getByRole("radio", { name: /OpenRouter/ })).toBeChecked()
    expect(within(section()).getByText("Key saved")).toBeInTheDocument()
    expect(
      within(section()).queryByLabelText("OpenRouter API key", {
        selector: "input",
      }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Replace" }))

    const input = screen.getByLabelText("OpenRouter API key")
    expect(input).toHaveAttribute("type", "password")
    expect(input).toHaveValue("")
  })

  it("reveals the Ollama fields and fills the model list from the API", async () => {
    serveOllamaModels()
    const user = await openSettings()
    expect(screen.queryByLabelText("Ollama address")).not.toBeInTheDocument()

    await user.click(screen.getByRole("radio", { name: /Ollama/ }))

    expect(screen.getByLabelText("Ollama address")).toHaveValue(
      "http://localhost:11434",
    )
    expect(
      await screen.findByRole("option", { name: /qwen2\.5:7b \(4\.7 GB\)/ }),
    ).toBeInTheDocument()
    expect(screen.queryByText("Key saved")).not.toBeInTheDocument()
  })

  it("shows why Ollama models cannot be listed", async () => {
    server.use(
      http.get("/api/models/ollama", () =>
        HttpResponse.json(
          {
            detail: "Ollama is not running at http://localhost:11434.",
            code: "model_error",
            hint: "Start it with `ollama serve`.",
          },
          { status: 502 },
        ),
      ),
    )
    const user = await openSettings()

    await user.click(screen.getByRole("radio", { name: /Ollama/ }))

    expect(
      await screen.findByText(/Ollama is not running.*ollama serve/),
    ).toBeInTheDocument()
  })

  it("saves the switch to Ollama and refreshes the library config", async () => {
    serveOllamaModels()
    const patches: unknown[] = []
    serveSaving(patches)
    let configReads = 0
    server.use(
      http.get("/api/config", () => {
        configReads += 1
        return HttpResponse.json(libraryConfig)
      }),
    )
    const user = await openSettings()
    await user.click(screen.getByRole("radio", { name: /Ollama/ }))
    await screen.findByRole("option", { name: /qwen2\.5:7b/ })
    const readsBeforeSave = configReads

    await user.selectOptions(screen.getByLabelText("Model"), "qwen2.5:7b")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([
      { script_provider: "ollama", ollama_model: "qwen2.5:7b" },
    ])
    expect(configReads).toBeGreaterThan(readsBeforeSave)
    expect(screen.getByRole("radio", { name: /Ollama/ })).toBeChecked()
  })

  it("sends a replaced key once and never shows it again", async () => {
    const patches: unknown[] = []
    serveSaving(patches)
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Replace" }))
    await user.type(screen.getByLabelText("OpenRouter API key"), "sk-or-new")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([{ openrouter_api_key: "sk-or-new" }])
    expect(within(section()).getByText("Key saved")).toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain("sk-or-new")
  })

  it("shows the latency when the connection test passes", async () => {
    serveCheck({
      is_reachable: true,
      provider: "openrouter",
      model: "anthropic/claude-haiku-5.5",
      latency_ms: 142.4,
    })
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Test connection" }))

    expect(
      await screen.findByText(
        "OK: anthropic/claude-haiku-5.5 answered · 142 ms.",
      ),
    ).toBeInTheDocument()
  })

  it("shows the error and hint in text when the connection test fails", async () => {
    serveCheck({
      is_reachable: false,
      provider: "openrouter",
      model: "anthropic/claude-haiku-5.5",
      error: "OpenRouter returned 402.",
      hint: "Add credits with OpenRouter or lower PHEMIUS_SCRIPT_MAX_TOKENS.",
    })
    const user = await openSettings()

    await user.click(screen.getByRole("button", { name: "Test connection" }))

    expect(
      await screen.findByText("Connection failed: OpenRouter returned 402."),
    ).toBeInTheDocument()
    expect(screen.getByText(/Add credits with OpenRouter/)).toBeInTheDocument()
  })

  it("saves unsaved changes before testing the connection", async () => {
    const patches: unknown[] = []
    serveSaving(patches)
    serveCheck({ is_reachable: true, provider: "openrouter", model: "x/y" })
    const user = await openSettings()

    const model = screen.getByLabelText("Model")
    await user.clear(model)
    await user.type(model, "x/y")
    await user.click(screen.getByRole("button", { name: "Test connection" }))

    expect(await screen.findByText(/OK: x\/y answered/)).toBeInTheDocument()
    expect(patches).toEqual([{ model: "x/y" }])
  })

  it("disables fields set by the environment and says why", async () => {
    server.use(
      settingsHandler(
        settingsOverview({
          values: {
            script_provider: {
              value: "openrouter",
              source: "env",
              is_locked: true,
            },
            model: { value: "a/b", source: "env", is_locked: true },
          },
        }),
      ),
    )
    await openSettings()

    expect(screen.getByRole("radio", { name: /Ollama/ })).toBeDisabled()
    expect(screen.getByLabelText("Model")).toBeDisabled()
    expect(
      screen.getByText(/provider is set by PHEMIUS_SCRIPT_PROVIDER/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/set by an environment variable on the server/),
    ).toBeInTheDocument()
  })

  it("saves the other fields when some are locked", async () => {
    const lockedValues = {
      script_provider: { value: "openrouter", source: "env", is_locked: true },
      model: { value: "a/b", source: "env", is_locked: true },
    } as const
    const patches: unknown[] = []
    server.use(
      settingsHandler(settingsOverview({ values: lockedValues })),
      http.patch("/api/settings", async ({ request }) => {
        patches.push(await request.json())
        return HttpResponse.json(settingsOverview({ values: lockedValues }))
      }),
    )
    const user = await openSettings()

    const limit = screen.getByLabelText("Longest script, in tokens")
    await user.clear(limit)
    await user.type(limit, "9000")
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(await screen.findByText("Saved.")).toBeInTheDocument()
    expect(patches).toEqual([{ script_max_tokens: 9000 }])
  })

  it("warns that a saved key follows a changed base URL", async () => {
    server.use(
      settingsHandler(
        settingsOverview({
          values: {
            script_provider: {
              value: "openai_compatible",
              source: "saved",
              is_locked: false,
            },
            script_base_url: {
              value: "http://localhost:1234/v1",
              source: "saved",
              is_locked: false,
            },
          },
          secrets: {
            script_api_key: {
              has_key: true,
              source: "saved",
              is_locked: false,
            },
          },
        }),
      ),
    )
    const user = await openSettings()
    const baseUrl = screen.getByLabelText("Base URL")
    expect(screen.queryByText(/saved key will be sent/)).not.toBeInTheDocument()

    await user.clear(baseUrl)
    await user.type(baseUrl, "https://other.example/v1")

    expect(screen.getByText(/saved key will be sent/)).toBeInTheDocument()
  })

  it("asks for a key before saving a provider that needs one", async () => {
    const patches: unknown[] = []
    serveSaving(patches)
    const user = await openSettings()

    await user.click(screen.getByRole("radio", { name: /^OpenAI Cloud/ }))
    await user.click(within(section()).getByRole("button", { name: "Save" }))

    expect(
      await screen.findByText("Error: Enter an API key."),
    ).toBeInTheDocument()
    expect(patches).toEqual([])
  })
})
