# Service-signal bindings (Phase-2 hook, e.g. tasks_management maker-checker).
# Intentionally a no-op in Phase 1; call bind_service_signals() from AppConfig.ready()
# when wiring approval workflows.

def bind_service_signals():
    pass
