async function tui(api: {
  keymap: {
    registerLayer(input: {
      commands: Array<{
        namespace: string
        name: string
        title: string
        category: string
        slashName: string
        run(): void
      }>
      bindings: never[]
    }): void
    dispatchCommand(name: string): void
  }
}) {
  api.keymap.registerLayer({
    commands: [
      {
        namespace: "palette",
        name: "session.clear",
        title: "Clear session",
        category: "Session",
        slashName: "clear",
        run() {
          api.keymap.dispatchCommand("session.new")
        },
      },
    ],
    bindings: [],
  })
}

export default {
  id: "clear-command",
  tui,
}
