import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest"
import { server } from "./mocks/server"

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
beforeEach(() => localStorage.clear())
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
