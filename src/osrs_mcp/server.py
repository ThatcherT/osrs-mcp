from mcp.server.fastmcp import FastMCP

mcp = FastMCP("osrs")

# Import tool modules to register them
import osrs_mcp.tools.player  # noqa: F401, E402
import osrs_mcp.tools.items  # noqa: F401, E402
import osrs_mcp.tools.monsters  # noqa: F401, E402
import osrs_mcp.tools.dps  # noqa: F401, E402
import osrs_mcp.tools.quests  # noqa: F401, E402
import osrs_mcp.tools.general  # noqa: F401, E402
import osrs_mcp.tools.hours  # noqa: F401, E402


def main():
    mcp.run()


if __name__ == "__main__":
    main()
