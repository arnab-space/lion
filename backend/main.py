import json
import urllib.parse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import asyncio
import traceback

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "message": "Bulletproof UI Automation Scraper is running."}

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--single-process", 
                    "--no-zygote",
                    "--window-size=1440,900"
                ]
            )
            
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            # 1. Navigate to base portal landing page
            base_url = f"https://www.ishoprewards.com/hotels/hotel-list?checkIn={checkin}&checkOut={checkout}&noOfRooms=1&city=Mumbai&country=IN&countryName=%20India&state=%20Maharashtra&scr=INR&sct=IN&room%5B0%5D=1&numberOfAdults%5B0%5D=2&numberOfChildren%5B0%5D=0&childrenAge%5B0%5D=&channel=web&locationSuggestion.id=357389&locationSuggestion.name=Mumbai&locationSuggestion.type=City&cachedContent=true&latitude=19.075986&longitude=72.877663&numberOfRooms=1&totalGuest=2&selectedAges="
            await page.goto(base_url, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            
            # 2. Clear T&C Popup if present
            try:
                tc_button = page.locator("button.ishop-popup-button").first
                await tc_button.wait_for(state="visible", timeout=4000)
                await tc_button.evaluate("el => el.click()")
                await asyncio.sleep(1.5)
            except Exception:
                pass
                
            # 3. UI Automation Sequence (Matches your working script)
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)

            loc_trigger = page.locator(".fontsize-16.text-capitalize.text-dark.fw_6.mb-0.text-truncate, .fontsize-16.text-truncate").first
            input_box = page.locator("input[placeholder*='Search'], input[class*='w-100'], .search-box input").first
            
            try:
                await loc_trigger.wait_for(state="visible", timeout=3000)
                await loc_trigger.evaluate("el => el.click()")
                await asyncio.sleep(1)
            except Exception:
                pass

            await input_box.wait_for(state="attached", timeout=5000)
            await input_box.evaluate("el => el.click()")
            await input_box.fill("")
            await input_box.type(city, delay=100)
            await asyncio.sleep(3) 

            dropdown = page.locator(".label-box, ul li .label-box, .suggestion-results li").first
            await dropdown.wait_for(state="attached", timeout=5000)
            await dropdown.evaluate("el => el.click()")
            await asyncio.sleep(1.5)

            search_btn = page.locator("button.searchbn_web, .searchbn_web").first
            await search_btn.wait_for(state="attached", timeout=5000)

            # 4. Inject Fetch Interceptor
            await page.evaluate("""() => {
                window.__captured_hotel_data = null; 
                const originalFetch = window.fetch;
                window.fetch = async function(...args) {
                    const response = await originalFetch.apply(this, args);
                    const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
                    if (url.toLowerCase().includes('listing') && args[1] && args[1].method && args[1].method.toUpperCase() === 'POST') {
                        const clone = response.clone();
                        clone.json().then(data => {
                            window.__captured_hotel_data = data;
                        }).catch(err => console.error(err));
                    }
                    return response;
                };
            }""")

            # 5. Click Search and wait for response
            await search_btn.evaluate("el => el.click()")
            await asyncio.sleep(20) # Wait for network telemetry capture

            raw_json_response = await page.evaluate("window.__captured_hotel_data")
            await browser.close()

            if raw_json_response and "response" in raw_json_response and "hotels" in raw_json_response["response"]:
                return {
                    "status": "success",
                    "error": None,
                    "hotels": raw_json_response["response"]["hotels"]
                }
            else:
                return {
                    "status": "failed",
                    "error": f"Telemetry engine bypassed extraction for {city}.",
                    "hotels": []
                }
            
    except Exception as e:
        print(traceback.format_exc())
        return {"status": "failed", "error": f"Backend Error: {str(e)}", "hotels": []}
