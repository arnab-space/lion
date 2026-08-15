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
    if city_key not in CITY_DATABASE: return None
    data = CITY_DATABASE[city_key]
    return (
        f"https://www.ishoprewards.com/hotels/hotel-list?checkIn={check_in}&checkOut={check_out}&noOfRooms=1"
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

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    target_url = generate_ishop_url(city, checkin, checkout)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await context.new_page()

            # Navigate and wait for network stability
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle") # Wait for Angular/React to finish loading
            
            # Clear Popup
            try:
                tc = page.locator("button.ishop-popup-button").first
                if await tc.is_visible(timeout=3000): await tc.click()
            except: pass

            # Locate button
            search_btn = page.locator("button.searchbn_web, .searchbn_web").first
            
            # WAIT FOR ENABLED STATE: Ensure the button is NOT disabled
            for _ in range(10):
                is_disabled = await search_btn.evaluate("el => el.disabled")
                if not is_disabled:
                    break
                await asyncio.sleep(1)

            # Capture API
            captured_data = {"status": "failed", "hotels": []}
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        json_data = await response.json()
                        if "response" in json_data:
                            captured_data.update({"status": "success", "hotels": json_data["response"].get("hotels", [])})
                    except: pass
            
            page.on("response", handle_response)
            
            # Click and wait
            await search_btn.click()
            await asyncio.sleep(10)

            await browser.close()
            return captured_data
    except Exception as e:
        return {"status": "failed", "error": str(e), "hotels": []}
