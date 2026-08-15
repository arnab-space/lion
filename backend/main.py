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
    # Get the correctly parameterized URL for the city
    target_url = generate_ishop_url(city, checkin, checkout)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # 1. Navigate to the fully generated, correct URL
            print(f"Navigating to: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # 2. Clear T&C Popup
            try:
                tc_button = page.locator("button.ishop-popup-button").first
                if await tc_button.is_visible(timeout=5000):
                    await tc_button.evaluate("el => el.click()")
            except: pass

            # 3. Trigger Search
            search_btn = page.locator("button.searchbn_web, .searchbn_web").first
            await search_btn.wait_for(state="visible", timeout=10000)

            # 4. Capture
            captured_data = {"status": "failed", "hotels": []}
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        json_data = await response.json()
                        if "response" in json_data:
                            captured_data.update({"status": "success", "hotels": json_data["response"].get("hotels", [])})
                    except: pass
            
            page.on("response", handle_response)
            await search_btn.evaluate("el => el.click()")
            
            for _ in range(15):
                if captured_data["status"] == "success": break
                await asyncio.sleep(1)

            await browser.close()
            return captured_data
            
    except Exception as e:
        return {"status": "failed", "error": str(e), "hotels": []}
