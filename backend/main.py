import json
import urllib.parse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import asyncio
import traceback

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

try:
    with open('city_database.json', 'r') as f:
        CITY_DATABASE = json.load(f)
except FileNotFoundError:
    CITY_DATABASE = {}

def generate_ishop_url(city_key, check_in, check_out):
    if city_key not in CITY_DATABASE:
        return None
    data = CITY_DATABASE[city_key]
    
    # We construct the URL with the exact parameters the iShop API requires
    params = {
        "checkIn": check_in,
        "checkOut": check_out,
        "noOfRooms": "1",
        "city": data.get("city", ""),
        "country": data.get("country", "IN"),
        "countryName": data.get("countryName", " India"),
        "state": data.get("state", ""),
        "scr": "INR",
        "sct": "IN",
        "channel": "web",
        "locationSuggestion.id": data.get("loc_id", ""),
        "locationSuggestion.name": data.get("loc_name", ""),
        "locationSuggestion.type": data.get("loc_type", "City"),
        "cachedContent": "true",
        "latitude": data.get("lat", ""),
        "longitude": data.get("lon", ""),
        "numberOfRooms": "1",
        "totalGuest": "2"
    }
    return f"https://www.ishoprewards.com/hotels/hotel-list?{urllib.parse.urlencode(params)}"

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    target_url = generate_ishop_url(city, checkin, checkout)
    if not target_url:
        return {"status": "failed", "error": f"City {city} not in database"}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            page = await context.new_page()

            # Set up the response listener BEFORE navigating
            captured_data = {"status": "failed", "hotels": []}
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        data = await response.json()
                        if "response" in data:
                            captured_data.update({"status": "success", "hotels": data["response"].get("hotels", [])})
                    except: pass
            
            page.on("response", handle_response)

            # Navigate and wait for the API to trigger automatically
            await page.goto(target_url, wait_until="domcontentloaded")
            
            # Wait up to 20 seconds for the network to respond with data
            for _ in range(20):
                if captured_data["status"] == "success": break
                await asyncio.sleep(1)
            
            await browser.close()
            return captured_data
    except Exception as e:
        return {"status": "failed", "error": str(e)}
