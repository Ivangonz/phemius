import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest"
import { stubMediaElement } from "./mediaElement"
import { server } from "./mocks/server"

beforeAll(() => {
  stubMediaElement()
  server.listen({ onUnhandledRequest: "error" })
})
beforeEach(() => localStorage.clear())
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
