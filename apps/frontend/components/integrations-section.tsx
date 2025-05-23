export function IntegrationsSection() {
  return (
    <section className="w-full py-12 md:py-24 lg:py-32 bg-muted">
      <div className="container px-4 md:px-6">
        <div className="flex flex-col items-center justify-center space-y-4 text-center">
          <div className="space-y-2">
            <div className="inline-block rounded-lg bg-primary/10 px-3 py-1 text-sm text-primary">Integrations</div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl">It Plays Nice with Your Stack</h2>
            <p className="max-w-[900px] text-muted-foreground md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              GridFlow seamlessly integrates with your favorite tools, making your workflow even smoother.
            </p>
          </div>
        </div>
        <div className="mx-auto mt-12 grid max-w-5xl grid-cols-2 gap-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {["Slack", "GitHub", "Google", "Dropbox", "Figma", "Notion", "Trello", "Asana", "Jira", "Zoom"].map(
            (integration) => (
              <div
                key={integration}
                className="flex flex-col items-center justify-center space-y-2 rounded-lg border bg-background p-4"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                  <span className="text-xl font-bold">{integration.charAt(0)}</span>
                </div>
                <span className="text-sm font-medium">{integration}</span>
              </div>
            ),
          )}
        </div>
      </div>
    </section>
  )
}
