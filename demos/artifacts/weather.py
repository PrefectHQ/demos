import httpx
from typing import Optional
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact


@task(retries=3, task_run_name="HTTP GET {url}")
def http_get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None, follow_redirects: bool = False) -> dict:
    """Generic task for making HTTP GET requests with error handling."""
    response = httpx.get(url, params=params, headers=headers, follow_redirects=follow_redirects)
    response.raise_for_status()
    return response.json()


@task(log_prints=True, task_run_name="Geocode Address")
def geocode_address(address: str) -> dict[str, float]:
    """Convert a US street address to latitude and longitude using the Census Geocoding API."""
    base_url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address": address,
        "benchmark": "4",  # Public_AR_Current
        "format": "json"
    }
    
    data = http_get(base_url, params=params)
    
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        raise ValueError(f"No geocoding results found for address: {address}")
    
    coordinates = matches[0]["coordinates"]
    latitude = coordinates["y"]
    longitude = coordinates["x"]
    
    print(f"Geocoded '{address}' to coordinates: ({latitude}, {longitude})")
    
    return {"latitude": latitude, "longitude": longitude}

@task(task_run_name="Format Table Row ({metric})")
def format_weather_table_row(weather: dict, metric: str, key: str, formatter=None) -> str | None:
    """Format a weather data row for the markdown table if value exists and is not None."""
    value = weather.get(key)
    if value is not None:
        formatted_value = formatter(value) if formatter else str(value)
        return f"| {metric} | {formatted_value} |\n"
    return None


@task(task_run_name="Build Weather Data Table")
def build_weather_data_table(weather: dict) -> str:
    """Build the weather data table section of the markdown artifact."""
    weather_metrics = [
        ("Temperature", "temperature", lambda t: f"{t['c']:.1f}°C ({t['f']:.1f}°F)"),
        ("Dewpoint", "dewpoint", lambda d: f"{d['c']:.1f}°C ({d['f']:.1f}°F)"),
        ("Relative Humidity", "humidity", lambda h: f"{h:.1f}%"),
        ("Wind Speed", "wind_speed", lambda ws: f"{ws:.1f} m/s ({ws * 2.237:.1f} mph)"),
        ("Wind Direction", "wind_direction", lambda wd: f"{wd:.0f}°"),
        ("Barometric Pressure", "barometric_pressure", lambda p: f"{p:.1f} Pa ({p / 3386.39:.2f} inHg)"),
        ("Visibility", "visibility", lambda v: f"{v:.0f} m ({v / 1609.34:.2f} mi)"),
    ]

    return "".join(
        row
        for metric, key, formatter in weather_metrics
        if (row := format_weather_table_row(weather, metric, key, formatter)) is not None
    )


@task(task_run_name="Create Weather Report")
def create_weather_report_artifact(result: dict) -> None:
    """Create a Markdown artifact with weather observations."""
    weather_markdown = f"""# Weather Observations

## Location
**Address:** {result['address']}
**Coordinates:** {result['coordinates']['latitude']:.6f}°N, {result['coordinates']['longitude']:.6f}°W

## Current Conditions
"""
    
    weather_markdown += f"**Observed at:** {result['weather']['station_id']}\n\n"
    
    if result['weather']['text_description']:
        weather_markdown += f"**Conditions:** {result['weather']['text_description']}\n\n"
    
    weather_markdown += "## Weather Data\n\n"
    weather_markdown += "| Metric | Value |\n"
    weather_markdown += "|:-------|------:|\n"
    weather_markdown += build_weather_data_table(result['weather'])
    
    if result['weather']['timestamp']:
        weather_markdown += f"\n**Observation Time:** {result['weather']['timestamp']}\n"
    
    create_markdown_artifact(
        key="weather-observations",
        markdown=weather_markdown,
        description=f"Weather observations for {result['address']}"
    )

@task(log_prints=True, task_run_name="Get Weather Observations at {latitude}, {longitude}")
def get_weather_observations(
    latitude: float, 
    longitude: float
) -> dict:
    """Fetch current weather observations from the Weather.gov API using latitude and longitude."""
    # Step 1: Get grid point information
    points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
    points_data = http_get(points_url, headers={"User-Agent": "Prefect Weather Flow"}, follow_redirects=True)
    
    properties = points_data["properties"]
    grid_id = properties["gridId"]
    grid_x = properties["gridX"]
    grid_y = properties["gridY"]
    
    print(f"Found grid point: {grid_id} at ({grid_x}, {grid_y})")
    
    # Step 2: Get observation stations for this grid point
    stations_url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/stations"
    stations_data = http_get(stations_url, headers={"User-Agent": "Prefect Weather Flow"}, follow_redirects=True)
    
    stations = stations_data.get("features", [])
    if not stations:
        raise ValueError(f"No observation stations found for grid point {grid_id} ({grid_x}, {grid_y})")
    
    station_id = stations[0]["properties"]["stationIdentifier"]
    print(f"Using observation station: {station_id}")
    
    # Step 3: Get latest observations from the station
    observations_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    observations_data = http_get(observations_url, headers={"User-Agent": "Prefect Weather Flow"}, follow_redirects=True)
    
    return {
        "properties": observations_data.get("properties", {}),
        "station_id": station_id
    }


@flow(log_prints=True, flow_run_name='Current weather for {address}')
def get_weather_for_address(
    address: str = "2112 Pennsylvania Ave NW, Washington, DC 20037",
) -> dict:
    """Prefect flow to get current weather observations for a given US street address."""
    print(f"Fetching weather for address: {address}")
    
    # Geocode the address to get coordinates
    coordinates = geocode_address(address)
    
    # Fetch weather observations using the coordinates
    observations_result = get_weather_observations(
        coordinates["latitude"],
        coordinates["longitude"]
    )
    
    weather_data = observations_result["properties"]
    station_id = observations_result["station_id"]
    
    # Extract and format key weather information
    # Temperature and dewpoint are in Celsius from the API
    temp_c = weather_data.get("temperature", {}).get("value")
    temp_f = (temp_c * 9/5 + 32) if temp_c is not None else None
    
    dewpoint_c = weather_data.get("dewpoint", {}).get("value")
    dewpoint_f = (dewpoint_c * 9/5 + 32) if dewpoint_c is not None else None
    
    result = {
        "address": address,
        "coordinates": coordinates,
        "weather": {
            "station_id": station_id,
            "temperature": {"c": temp_c, "f": temp_f} if temp_c is not None else None,
            "dewpoint": {"c": dewpoint_c, "f": dewpoint_f} if dewpoint_c is not None else None,
            "humidity": weather_data.get("relativeHumidity", {}).get("value"),
            "wind_speed": weather_data.get("windSpeed", {}).get("value"),
            "wind_direction": weather_data.get("windDirection", {}).get("value"),
            "barometric_pressure": weather_data.get("barometricPressure", {}).get("value"),
            "visibility": weather_data.get("visibility", {}).get("value"),
            "text_description": weather_data.get("textDescription"),
            "timestamp": weather_data.get("timestamp"),
        }
    }
    
    print(f"Weather observation retrieved successfully")
    if result['weather']['temperature']:
        temp = result['weather']['temperature']
        print(f"Temperature: {temp['c']:.1f}°C ({temp['f']:.1f}°F)")
    if result['weather']['text_description']:
        print(f"Conditions: {result['weather']['text_description']}")
    
    # Create a Markdown artifact with the weather observations
    create_weather_report_artifact(result)
    
    return result


if __name__ == "__main__":
    # Example usage
    result = get_weather_for_address()
    print("\n=== Full Weather Data ===")
    print(result)

