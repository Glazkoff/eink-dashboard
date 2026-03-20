"""Context providers for fetching real data to fill dashboards."""
import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx


class ContextProvider(ABC):
    """Base class for context providers."""
    
    name: str = "base"
    
    @abstractmethod
    async def fetch(self) -> dict:
        """Fetch context data."""
        pass


class WeatherProvider(ContextProvider):
    """Fetch weather data from wttr.in or Open-Meteo."""
    
    name = "weather"
    
    def __init__(self, location: str = "Moscow", units: str = "metric"):
        self.location = location
        self.units = units
    
    async def fetch(self) -> dict:
        """Fetch current weather and forecast."""
        # Using wttr.in (no API key needed)
        url = f"https://wttr.in/{self.location}?format=j1"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
        
        current = data.get("current_condition", [{}])[0]
        
        return {
            "location": self.location,
            "temperature": current.get("temp_C", "N/A"),
            "condition": current.get("weatherDesc", [{}]).get("value", "Unknown"),
            "humidity": current.get("humidity", "N/A"),
            "wind": current.get("windspeedKmph", "N/A"),
            "forecast": self._parse_forecast(data),
        }
    
    def _parse_forecast(self, data: dict) -> list:
        """Parse 3-day forecast."""
        forecast = []
        for day in data.get("weather", [])[:3]:
            forecast.append({
                "date": day.get("date", ""),
                "max_temp": day.get("maxtempC", "N/A"),
                "min_temp": day.get("mintempC", "N/A"),
                "condition": day.get("hourly", [{}])[0].get("weatherDesc", [{}]).get("value", "Unknown"),
            })
        return forecast


class CalendarProvider(ContextProvider):
    """Fetch calendar events (stub - needs real implementation)."""
    
    name = "calendar"
    
    def __init__(self, days_ahead: int = 1):
        self.days_ahead = days_ahead
    
    async def fetch(self) -> dict:
        """Fetch upcoming calendar events.
        
        NOTE: This is a stub. Implement with:
        - Google Calendar API
        - Apple Calendar
        - Outlook
        - CalDAV
        - Local .ics files
        """
        # Stub data for now
        return {
            "events": [
                {
                    "time": "10:00",
                    "title": "Team Standup",
                    "duration": 30,
                },
                {
                    "time": "14:00",
                    "title": "Project Review",
                    "duration": 60,
                },
            ],
            "date": datetime.now().strftime("%A, %B %d"),
        }


class NewsProvider(ContextProvider):
    """Fetch news headlines."""
    
    name = "news"
    
    def __init__(self, sources: list[str] = None, max_items: int = 5):
        self.sources = sources or ["bbc", "techcrunch"]
        self.max_items = max_items
    
    async def fetch(self) -> dict:
        """Fetch news headlines.
        
        NOTE: This is a stub. Implement with:
        - NewsAPI
        - RSS feeds
        - Hacker News API
        """
        # Stub data
        return {
            "headlines": [
                {"title": "AI Breakthrough in Language Models", "source": "TechCrunch"},
                {"title": "New Climate Initiative Announced", "source": "BBC"},
                {"title": "Tech Stocks Rise on Earnings", "source": "Reuters"},
            ],
            "updated": datetime.now().strftime("%H:%M"),
        }


class TasksProvider(ContextProvider):
    """Fetch tasks from todo systems."""
    
    name = "tasks"
    
    def __init__(self, max_items: int = 5):
        self.max_items = max_items
    
    async def fetch(self) -> dict:
        """Fetch pending tasks.
        
        NOTE: This is a stub. Implement with:
        - Todoist API
        - Notion API
        - Apple Reminders
        - Local files
        """
        return {
            "tasks": [
                {"title": "Review PR #42", "priority": "high"},
                {"title": "Update documentation", "priority": "medium"},
                {"title": "Schedule team meeting", "priority": "low"},
            ],
            "count": 3,
        }


class TimeProvider(ContextProvider):
    """Provide current time and date."""
    
    name = "time"
    
    async def fetch(self) -> dict:
        now = datetime.now()
        return {
            "time": now.strftime("%H:%M"),
            "date": now.strftime("%A, %B %d, %Y"),
            "weekday": now.strftime("%A"),
            "week_number": now.isocalendar()[1],
            "generated_at": now.strftime("%H:%M"),
            "note": "Time when dashboard was generated (not real-time clock)",
        }


class QuoteProvider(ContextProvider):
    """Fetch inspirational quote."""
    
    name = "quote"
    
    async def fetch(self) -> dict:
        """Fetch a random quote."""
        # Using quotable.io (no API key)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.quotable.io/random",
                    timeout=5.0
                )
                data = response.json()
                return {
                    "text": data.get("content", ""),
                    "author": data.get("author", "Unknown"),
                }
        except Exception:
            return {
                "text": "The only way to do great work is to love what you do.",
                "author": "Steve Jobs",
            }


# Registry of all providers
PROVIDERS: dict[str, type[ContextProvider]] = {
    "weather": WeatherProvider,
    "calendar": CalendarProvider,
    "news": NewsProvider,
    "tasks": TasksProvider,
    "time": TimeProvider,
    "quote": QuoteProvider,
}


def get_provider(name: str, **kwargs) -> Optional[ContextProvider]:
    """Get a provider instance by name."""
    provider_class = PROVIDERS.get(name)
    if provider_class:
        return provider_class(**kwargs)
    return None


async def fetch_contexts(
    provider_names: list[str],
    provider_configs: Optional[dict] = None,
) -> dict:
    """Fetch data from multiple providers.
    
    Args:
        provider_names: List of provider names to fetch from
        provider_configs: Optional dict of {provider_name: {kwargs}}
    
    Returns:
        Dict with all fetched context data
    """
    contexts = {}
    provider_configs = provider_configs or {}
    
    async def fetch_provider(name: str):
        config = provider_configs.get(name, {})
        provider = get_provider(name, **config)
        if provider:
            try:
                return name, await provider.fetch()
            except Exception as e:
                return name, {"error": str(e)}
        return name, {"error": f"Provider '{name}' not found"}
    
    # Fetch all providers in parallel
    results = await asyncio.gather(*[
        fetch_provider(name) for name in provider_names
    ])
    
    for name, data in results:
        contexts[name] = data
    
    return contexts
