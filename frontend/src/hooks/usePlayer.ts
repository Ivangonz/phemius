import { useContext } from "react"
import {
  PlayerContext,
  PlayerProgressContext,
  type Player,
  type PlayerProgress,
} from "@/components/player/playerContext"

export function usePlayer(): Player {
  const player = useContext(PlayerContext)
  if (!player) throw new Error("usePlayer must be used inside PlayerProvider")
  return player
}

export function usePlayerProgress(): PlayerProgress {
  return useContext(PlayerProgressContext)
}
