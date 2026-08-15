import json
import urllib.parse
import re
import os
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

def fix_date(date_str):
    if re.match(r"^\d{2}-\d{2}-\d{4}$", date_str):
        parts = date_str.split("-")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str

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
        f"&cachedContent=false&latitude={data.get('lat', '')}&longitude={data.get('lon', '')}"
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
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-cache",
                    "--disk-cache-size=0",
                    "--disable-gpu", # EXTRA MEMORY SAVING
                    "--no-zygote"    # EXTRA MEMORY SAVING
                ]
            )
            
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            
            connect_sid = os.environ.get("CONNECT_SID", "")
            if connect_sid:
                await context.add_cookies([{
                    "name": "connect.sid",
                    "value": connect_sid,
                    "domain": "www.ishoprewards.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True
                }])
            
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            # --- MASSIVE MEMORY SAVER: BLOCK IMAGES, FONTS, AND CSS ---
            async def intercept_route(route):
                if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", intercept_route)
            # ----------------------------------------------------------

            captured_data = {"status": "failed", "hotels": []}
            
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        data = await response.json()
                        if "response" in data and "hotels" in data["response"]:
                            if len(data["response"]["hotels"]) > 0:
                                captured_data["status"] = "success"
                                captured_data["hotels"] = data["response"]["hotels"]
                    except: pass
            
            page.on("response", handle_response)

            await page.goto(target_url, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            
            try:
                tc = page.locator("button.ishop-popup-button").first
                if await tc.is_visible(timeout=3000):
                    await tc.click(force=True)
            except: pass
            
            try:
                search_btn = page.locator("button.searchbn_web").first
                if await search_btn.is_visible(timeout=3000):
                    await search_btn.click(force=True)
            except: pass
            
            for _ in range(30):
                if captured_data["status"] == "success" and len(captured_data["hotels"]) > 0: 
                    break
                await asyncio.sleep(1)
            
            await browser.close()
            
            if len(captured_data["hotels"]) == 0:
                captured_data["error"] = "Website returned 0 hotels. Render IP might be blocked without a proxy."
                
            return captured_data
            
    except Exception as e:
        return {"status": "failed", "error": str(e), "hotels": []}
