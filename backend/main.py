import json
import asyncio
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    with open('city_database.json', 'r') as f:
        CITY_DATABASE = json.load(f)
except FileNotFoundError:
    CITY_DATABASE = {}

@app.get("/")
async def root():
    return {"status": "online", "message": "Automation Engine is running."}

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
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

            # 1. Start at the root to ensure cookies are set
            await page.goto("https://www.ishoprewards.com/hotels/hotel-list", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            # 2. Clear T&C Popup
            try:
                tc_button = page.locator("button.ishop-popup-button").first
                if await tc_button.is_visible(timeout=3000):
                    await tc_button.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # 3. Input City
            loc_trigger = page.locator(".fontsize-16.text-capitalize.text-dark.fw_6.mb-0.text-truncate, .fontsize-16.text-truncate").first
            input_box = page.locator("input[placeholder*='Search'], input[class*='w-100'], .search-box input").first
            
            if await loc_trigger.is_visible(timeout=3000):
                await loc_trigger.click()
                await asyncio.sleep(1)

            await input_box.fill("")
            await input_box.type(city, delay=100)
            await asyncio.sleep(2) # Allow dropdown to load

            dropdown = page.locator(".label-box, ul li .label-box, .suggestion-results li").first
            await dropdown.click()
            await asyncio.sleep(1)

            # 4. Prepare Interceptor
            captured_data = {"status": "failed", "error": "API payload not captured", "hotels": []}
            
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        json_data = await response.json()
                        if "response" in json_data and "hotels" in json_data["response"]:
                            captured_data["status"] = "success"
                            captured_data["hotels"] = json_data["response"]["hotels"]
                    except: pass

            page.on("response", handle_response)
            
            # 5. Click Search
            search_btn = page.locator("button.searchbn_web, .searchbn_web").first
            await search_btn.click()
            
            # Wait for response
            for _ in range(15):
                if captured_data["status"] == "success": break
                await asyncio.sleep(1)

            await browser.close()
            return captured_data
            
    except Exception as e:
        print(traceback.format_exc())
        return {"status": "failed", "error": str(e), "hotels": []}
