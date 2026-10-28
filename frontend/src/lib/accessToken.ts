// Phemius has no accounts: one optional server token, kept in this browser so
// a phone on the LAN only has to enter it once.
const STORAGE_KEY = "phemius.accessToken"

export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}

export function setAccessToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token)
}
