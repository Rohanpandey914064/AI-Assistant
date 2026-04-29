"""
MCP Server — FastMCP Tool Registry
====================================
This server exposes all Sentinel-Agent tools via the Model Context Protocol.
Any MCP-compliant host (Claude Desktop, Cursor, etc.) can connect to this
server and use these tools without any code changes.

This also acts as the tool catalog for the internal ReAct agent — it reads
tool definitions from here to inject into the LLM system prompt.
"""

from fastmcp import FastMCP
from backend.mcp.tools import db_tool, api_tool, calc_tool
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Initialize FastMCP Server
# ============================================================

mcp = FastMCP(
    name="sentinel-agent-tools"
)


# ============================================================
# Register Tools with MCP
# ============================================================

@mcp.tool()
def save_preference(key: str, value: str) -> dict:
    """
    Save or update a user preference in the database.
    Use this when the user wants to remember something personal
    (e.g., preferred city, temperature unit, language, etc.).

    Args:
        key:   The preference name (e.g., 'city', 'unit', 'language')
        value: The preference value (e.g., 'Delhi', 'Celsius', 'Hindi')
    """
    return db_tool.save_preference(key, value)


@mcp.tool()
def get_preference(key: str) -> dict:
    """
    Retrieve a specific user preference from the database.
    Use this before performing actions where user preferences matter
    (e.g., look up preferred city before fetching weather).

    Args:
        key: The preference name to look up (e.g., 'city', 'unit')
    """
    return db_tool.get_preference(key)


@mcp.tool()
def list_preferences() -> dict:
    """
    List all stored user preferences from the database.
    Use this when the user asks 'what do you know about me?' or
    'what have you remembered?'
    """
    return db_tool.list_preferences()


@mcp.tool()
def delete_preference(key: str) -> dict:
    """
    Delete a specific user preference from the database.
    Use this when the user says 'forget my X preference' or
    'remove my stored city'.

    Args:
        key: The preference name to delete.
    """
    return db_tool.delete_preference(key)


@mcp.tool()
async def get_weather(city: str) -> dict:
    """
    Get current weather information for a city.
    Use this when the user asks about current weather, temperature,
    or conditions in any city.

    Args:
        city: The name of the city (e.g., 'Delhi', 'London', 'New York')
    """
    return await api_tool.get_weather(city)


@mcp.tool()
async def get_news(topic: str = "technology") -> dict:
    """
    Fetch the latest news headlines for a given topic.
    Use this when the user asks about recent news, current events,
    or wants to know what's happening in a specific domain.

    Args:
        topic: The news topic or keyword (e.g., 'AI', 'technology', 'India', 'finance')
    """
    return await api_tool.get_news(topic)


@mcp.tool()
def calculate(expression: str) -> dict:
    """
    Safely evaluate a mathematical expression.
    Use this for any arithmetic, algebraic, or trigonometric calculations.
    Supported: +, -, *, /, **, sqrt, sin, cos, log, abs, round, pi, e.

    Args:
        expression: A math expression string (e.g., 'sqrt(144) + 5 * 2', '25 * 48')

    IMPORTANT: Only use for math. Do not pass code, SQL, or system commands.
    """
    return calc_tool.calculate(expression)


# ============================================================
# Tool Schema Export (for ReAct agent system prompt)
# ============================================================

TOOL_DEFINITIONS = [
    {
        "name": "save_preference",
        "description": "Save or update a user preference (e.g., city, unit, language). Use when user wants to remember something.",
        "parameters": {"key": "string (preference name)", "value": "string (preference value)"},
    },
    {
        "name": "get_preference",
        "description": "Retrieve a specific user preference by key. Use before personalized actions.",
        "parameters": {"key": "string (preference name to look up)"},
    },
    {
        "name": "list_preferences",
        "description": "List all stored user preferences. Use when user asks what the agent remembers.",
        "parameters": {},
    },
    {
        "name": "delete_preference",
        "description": "Delete a user preference. Use when user says 'forget my X'.",
        "parameters": {"key": "string (preference name to delete)"},
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a city. Use for any weather-related queries.",
        "parameters": {"city": "string (city name, e.g., 'Delhi', 'London')"},
    },
    {
        "name": "get_news",
        "description": "Get latest news headlines for a topic. Use for current events queries.",
        "parameters": {"topic": "string (topic or keyword, default: 'technology')"},
    },
    {
        "name": "calculate",
        "description": "Safely evaluate math expressions. Use for arithmetic, algebra, trig calculations.",
        "parameters": {"expression": "string (e.g., 'sqrt(144) + 5 * 2')"},
    },
]
