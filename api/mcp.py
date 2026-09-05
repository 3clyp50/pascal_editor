"""Session/CSRF-protected maintenance for the bundled MCP; no custom UI."""
from helpers.api import ApiHandler, Request
from usr.plugins.pascal_editor.helpers import mcp


class PascalMCP(ApiHandler):
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict:
        action = (input or {}).get("action", "status")
        if action == "install":
            return mcp.install()
        if action != "status":
            raise ValueError("Unknown action; expected status or install")
        from helpers.mcp_handler import MCPConfig

        entries = [entry for entry in MCPConfig.get_instance().get_servers_status()
                   if entry["name"] == mcp.NAME]
        return {"server": mcp.NAME, "status": entries}
