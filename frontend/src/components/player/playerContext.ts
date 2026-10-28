import { createContext } from "react"

export const SKIP_BACK_SECONDS = 15
export const SKIP_FORWARD_SECONDS = 30

export type Track = {
  audioId: number
  title: string
  meta: string
}

export type Player = {
  track: Track | null
  isPlaying: boolean
  hasError: boolean
  playbackRate: number
  play: (track?: Track) => void
  pause: () => void
  toggle: () => void
  seek: (seconds: number) => void
  skip: (deltaSeconds: number) => void
  cycleSpeed: () => void
}

export type PlayerProgress = {
  currentTime: number
  duration: number
}

export const PlayerContext = createContext<Player | null>(null)

// Progress ticks several times a second; keeping it in its own context means
// list rows that only read `usePlayer()` do not re-render while audio plays.
export const PlayerProgressContext = createContext<PlayerProgress>({
  currentTime: 0,
  duration: 0,
})
