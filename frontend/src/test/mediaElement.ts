export const TEST_AUDIO_DURATION = 378

// happy-dom has no media pipeline: give loaded audio a fixed length and report
// seeks with `timeupdate`, as browsers do.
export function stubMediaElement(): void {
  const proto = HTMLMediaElement.prototype
  const currentTime = Object.getOwnPropertyDescriptor(proto, "currentTime")
  Object.defineProperty(proto, "duration", {
    configurable: true,
    get(this: HTMLMediaElement) {
      return this.getAttribute("src") ? TEST_AUDIO_DURATION : NaN
    },
  })
  Object.defineProperty(proto, "currentTime", {
    configurable: true,
    get(this: HTMLMediaElement) {
      return currentTime?.get?.call(this)
    },
    set(this: HTMLMediaElement, seconds: number) {
      currentTime?.set?.call(this, seconds)
      this.dispatchEvent(new Event("timeupdate"))
    },
  })
}
