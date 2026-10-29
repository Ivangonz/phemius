import { useFormContext, useWatch } from "react-hook-form"
import {
  findProvider,
  isLocked,
  savedValue,
  type ScriptModelFormValues,
  type SettingsOverview,
} from "@/lib/scriptModelSettings"
import { OllamaModelField } from "./OllamaModelField"
import { SecretField } from "./SecretField"
import { TextSettingField } from "./TextSettingField"

type ProviderFieldsProps = { overview: SettingsOverview }

const KEY_LABELS = {
  openrouter_api_key: "OpenRouter API key",
  openai_api_key: "OpenAI API key",
  script_api_key: "Server API key",
}

export function ProviderFields({ overview }: ProviderFieldsProps) {
  const { control } = useFormContext<ScriptModelFormValues>()
  const [providerId, baseUrl] = useWatch({
    control,
    name: ["script_provider", "script_base_url"],
  })
  const provider = findProvider(providerId)
  if (!provider) return null
  const has = (field: string) => provider.fields.some((item) => item === field)
  const locked = (key: string) => isLocked(overview, key)
  const keyField = provider.keyField
  // Until #85 is fixed, a saved key follows a changed base URL to the new host.
  const isKeyMoving =
    provider.id === "openai_compatible" &&
    overview.secrets.script_api_key?.has_key === true &&
    baseUrl.trim() !== savedValue(overview, "script_base_url")

  return (
    <div className="flex flex-col gap-4.5">
      {has("ollama_url") && (
        <TextSettingField
          name="ollama_url"
          label="Ollama address"
          isLocked={locked("ollama_url")}
          placeholder="http://localhost:11434"
        />
      )}
      {has("ollama_model") && (
        <OllamaModelField isLocked={locked("ollama_model")} />
      )}
      {has("script_base_url") && (
        <TextSettingField
          name="script_base_url"
          label="Base URL"
          isLocked={locked("script_base_url")}
          placeholder="http://localhost:1234/v1"
          description={
            isKeyMoving
              ? "Warning: the saved key will be sent to this new address. Replace the key if it belongs to another server."
              : undefined
          }
        />
      )}
      {keyField && (
        <SecretField
          name={keyField}
          label={KEY_LABELS[keyField]}
          status={overview.secrets[keyField]}
          isOptional={!provider.isKeyRequired}
        />
      )}
      {has("model") && (
        <TextSettingField
          name="model"
          label="Model"
          isLocked={locked("model")}
          placeholder={
            provider.id === "openai"
              ? "gpt-4.1-mini"
              : "anthropic/claude-sonnet-4.5"
          }
        />
      )}
      {provider.id === "offline" && (
        <p className="text-secondary text-muted">
          No model or key needed. Scripts read like the original text, so choose
          a model for natural-sounding narration.
        </p>
      )}
    </div>
  )
}
