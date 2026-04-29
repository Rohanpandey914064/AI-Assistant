"""
MCP Tool: External API — Weather & News
========================================
Fetches live data from OpenWeatherMap and NewsAPI.
Implements exponential backoff for resilience against rate limits / 5xx errors.
Falls back to realistic mock data when API keys are not configured.

Tools exposed:
    - get_weather(city)
    - get_news(topic)
"""

import httpx
import asyncio
import logging
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ============================================================
# Mock Data (used when API keys are not configured)
# ============================================================

MOCK_WEATHER: dict[str, dict] = {
    "delhi": {"city": "Delhi", "temperature": "34°C", "condition": "Sunny", "humidity": "45%", "wind": "12 km/h NW"},
    "mumbai": {"city": "Mumbai", "temperature": "31°C", "condition": "Partly Cloudy", "humidity": "78%", "wind": "18 km/h SW"},
    "bangalore": {"city": "Bangalore", "temperature": "26°C", "condition": "Cloudy", "humidity": "65%", "wind": "10 km/h SE"},
    "london": {"city": "London", "temperature": "14°C", "condition": "Rainy", "humidity": "85%", "wind": "22 km/h W"},
    "new york": {"city": "New York", "temperature": "22°C", "condition": "Clear", "humidity": "55%", "wind": "15 km/h NE"},
}

MOCK_NEWS: list[dict] = [
    {"title": "AI Agents Are Transforming Enterprise Workflows in 2025", "source": "TechCrunch", "url": "https://techcrunch.com"},
    {"title": "Model Context Protocol (MCP) Becomes Industry Standard for AI Tool Integration", "source": "The Verge", "url": "https://theverge.com"},
    {"title": "OpenAI Releases GPT-5 with Enhanced Reasoning Capabilities", "source": "Wired", "url": "https://wired.com"},
    {"title": "India's Tech Sector Surges as AI Adoption Accelerates", "source": "Economic Times", "url": "https://economictimes.com"},
    {"title": "Prompt Injection: The Top Security Threat for Enterprise AI Systems", "source": "SecurityWeek", "url": "https://securityweek.com"},
]


# ============================================================
# Retry Decorator (Exponential Backoff)
# ============================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
)
async def _fetch_with_retry(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    """HTTP GET with automatic exponential backoff on timeout or server errors."""
    response = await client.get(url, params=params, timeout=10.0)
    response.raise_for_status()
    return response.json()


# ============================================================
# Tool Functions
# ============================================================

async def get_weather(city: str) -> dict:
    """
    Get current weather for a city.

    Args:
        city: Name of the city (e.g., "Delhi", "London")

    Returns:
        dict with temperature, condition, humidity, and wind speed.
    """
    city = city.strip()

    # Use mock data if API key is not configured
    if settings.mock_apis or settings.openweather_api_key == "mock":
        mock_key = city.lower()
        if mock_key in MOCK_WEATHER:
            logger.info(f"API Tool (mock): Weather for {city}")
            return {"success": True, "data": MOCK_WEATHER[mock_key], "source": "mock"}

        # Generic mock for unknown cities
        return {
            "success": True,
            "data": {"city": city, "temperature": f"{random.randint(15, 40)}°C",
                     "condition": random.choice(["Sunny", "Cloudy", "Partly Cloudy", "Rainy"]),
                     "humidity": f"{random.randint(40, 90)}%", "wind": f"{random.randint(5, 30)} km/h"},
            "source": "mock",
        }

    # Live API call
    try:
        async with httpx.AsyncClient() as client:
            data = await _fetch_with_retry(
                client,
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": settings.openweather_api_key, "units": "metric"},
            )

        result = {
            "city": data["name"],
            "temperature": f"{data['main']['temp']:.1f}°C",
            "condition": data["weather"][0]["description"].capitalize(),
            "humidity": f"{data['main']['humidity']}%",
            "wind": f"{data['wind']['speed']} m/s",
        }
        logger.info(f"API Tool: Live weather for {city} fetched.")
        return {"success": True, "data": result, "source": "openweathermap"}

    except httpx.HTTPStatusError as e:
        logger.error(f"API Tool weather error for {city}: {e.response.status_code}")
        return {"success": False, "error": f"Weather API error: {e.response.status_code}"}

    except Exception as e:
        logger.error(f"API Tool weather unexpected error: {e}")
        return {"success": False, "error": str(e)}


async def get_news(topic: str = "technology") -> dict:
    """
    Fetch the latest news headlines for a given topic.

    Args:
        topic: The news topic to search (e.g., "AI", "technology", "finance")

    Returns:
        dict with a list of news articles (title, source, url).
    """
    topic = topic.strip()

    # Use mock data if API key is not configured
    if settings.mock_apis or settings.news_api_key == "mock":
        logger.info(f"API Tool (mock): News for topic '{topic}'")
        return {
            "success": True,
            "topic": topic,
            "articles": MOCK_NEWS[:3],
            "source": "mock",
        }

    # Live API call
    try:
        async with httpx.AsyncClient() as client:
            data = await _fetch_with_retry(
                client,
                "https://newsapi.org/v2/everything",
                params={
                    "q": topic,
                    "apiKey": settings.news_api_key,
                    "sortBy": "publishedAt",
                    "pageSize": 5,
                    "language": "en",
                },
            )

        articles = [
            {"title": a["title"], "source": a["source"]["name"], "url": a["url"]}
            for a in data.get("articles", [])
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]

        logger.info(f"API Tool: Live news for '{topic}' — {len(articles)} articles.")
        return {"success": True, "topic": topic, "articles": articles, "source": "newsapi"}

    except httpx.HTTPStatusError as e:
        logger.error(f"API Tool news error for '{topic}': {e.response.status_code}")
        return {"success": False, "error": f"News API error: {e.response.status_code}"}

    except Exception as e:
        logger.error(f"API Tool news unexpected error: {e}")
        return {"success": False, "error": str(e)}
