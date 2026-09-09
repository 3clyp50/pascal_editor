"""Initialize Pascal through its lifecycle hook before framework MCP startup."""
from helpers.extension import Extension


class PascalEditorBootExtension(Extension):
    def execute(self, **kwargs):
        from helpers.print_style import PrintStyle
        from usr.plugins.pascal_editor import hooks

        try:
            hooks.install(activate=False)
        except Exception as exc:
            PrintStyle.warning(f"Pascal Editor setup failed: {exc}")
