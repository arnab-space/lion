import json
import urllib.parse
import re
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

# Ensure dates are ALWAYS YYYY-MM-DD
def fix_date(date_str):
    if re.match(r"^\d{2}-\d{2}-\d{4}$", date_str):
        parts = date_str.split("-")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str

def generate_ishop_url(city_key, check_in, check_out):
    if city_key not in CITY_DATABASE:
        return None
    data = CITY_DATABASE[city_key]
    
    # We MUST use the exact raw string format to keep the [0] arrays intact for adults/rooms
    url = (
        f"https://www.ishoprewards.com/hotels/hotel-list?"
        f"checkIn={check_in}&checkOut={check_out}&noOfRooms=1"
        f"&city={urllib.parse.quote(data.get('city', ''))}&country={data.get('country', '')}"
        f"&countryName={urllib.parse.quote(data.get('countryName', ''))}"
        f"&state={urllib.parse.quote(data.get('state', ''))}&scr=INR&sct=IN&room%5B0%5D=1"
        f"&numberOfAdults%5B0%5D=2&numberOfChildren%5B0%5D=0&childrenAge%5B0%5D="
        f"&channel=web&locationSuggestion.id={data.get('loc_id', '')}"
        f"&locationSuggestion.name={urllib.parse.quote(data.get('loc_name', ''))}"
        f"&locationSuggestion.type={data.get('loc_type', '')}"
        f"&cachedContent=true&latitude={data.get('lat', '')}&longitude={data.get('lon', '')}"
        f"&numberOfRooms=1&totalGuest=2&selectedAges="
    )
    return url

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    checkin = fix_date(checkin)
    checkout = fix_date(checkout)
    
    target_url = generate_ishop_url(city, checkin, checkout)
    if not target_url:
        return {"status": "failed", "error": f"City {city} not in database"}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            page = await context.new_page()

            captured_data = {"status": "failed", "hotels": []}
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        data = await response.json()
                        if "response" in data:
                            captured_data.update({"status": "success", "hotels": data["response"].get("hotels", [])})
                    except: pass
            
            page.on("response", handle_response)

            await page.goto(target_url, wait_until="domcontentloaded")
            
            # Failsafe: if the SPA doesn't auto-fetch the hotels, force click the search button
            try:
                search_btn = page.locator("button.searchbn_web").first
                if await search_btn.is_visible(timeout=4000):
                    await search_btn.click()
            except: pass
            
            # Wait up to 20 seconds. If it successfully grabs a list of hotels early, break out instantly!
            for _ in range(20):
                if captured_data["status"] == "success" and len(captured_data["hotels"]) > 0: 
                    break
                await asyncio.sleep(1)
            
            await browser.close()
            return captured_data
    except Exception as e:
        return {"status": "failed", "error": str(e), "hotels": []}
