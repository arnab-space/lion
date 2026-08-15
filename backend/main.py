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

try:
    with open('city_database.json', 'r') as f:
        CITY_DATABASE = json.load(f)
except FileNotFoundError:
    CITY_DATABASE = {}

def generate_ishop_url(city_key, check_in, check_out):
    if city_key not in CITY_DATABASE:
        return None
        
    data = CITY_DATABASE[city_key]
    state_encoded = urllib.parse.quote(data.get("state", ""))
    country_name_encoded = urllib.parse.quote(data.get("countryName", ""))
    loc_name_encoded = urllib.parse.quote(data.get("loc_name", ""))
    city_encoded = urllib.parse.quote(data.get("city", ""))
    
    url = (
        f"https://www.ishoprewards.com/hotels/hotel-list?"
        f"checkIn={check_in}&checkOut={check_out}&noOfRooms=1"
        f"&city={city_encoded}&country={data.get('country', '')}&countryName={country_name_encoded}"
        f"&state={state_encoded}&scr=INR&sct=IN&room%5B0%5D=1"
        f"&numberOfAdults%5B0%5D=2&numberOfChildren%5B0%5D=0&childrenAge%5B0%5D="
        f"&channel=web&locationSuggestion.id={data.get('loc_id', '')}"
        f"&locationSuggestion.name={loc_name_encoded}&locationSuggestion.type={data.get('loc_type', '')}"
        f"&cachedContent=true&latitude={data.get('lat', '')}&longitude={data.get('lon', '')}"
        f"&numberOfRooms=1&totalGuest=2&selectedAges="
    )
    return url

@app.get("/")
async def root():
    return {"status": "online", "message": "Playwright Scraper API is actively running."}

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    target_url = generate_ishop_url(city, checkin, checkout)
    
    if not target_url:
        return {"status": "failed", "error": f"City '{city}' not found in database.", "hotels": []}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-dev-shm-usage",
                    "--single-process", 
                    "--no-zygote",
                    "--disable-blink-features=AutomationControlled"
                ] 
            )
            
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()
            
            captured_data = {"status": "failed", "error": "Telemetry engine bypassed extraction or page timed out.", "hotels": []}
            
            async def handle_response(response):
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        json_data = await response.json()
                        if "response" in json_data and "hotels" in json_data["response"]:
                            captured_data["status"] = "success"
                            captured_data["error"] = None
                            captured_data["hotels"] = json_data["response"]["hotels"]
                    except Exception:
                        pass

            page.on("response", handle_response)
            
            # Navigate directly to the fully constructed URL
            await page.goto(target_url, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            
            # Handle T&C Popup if it appears
            try:
                tc_button = page.locator("button.ishop-popup-button").first
                await tc_button.wait_for(state="visible", timeout=5000)
                await tc_button.evaluate("el => el.click()")
                await asyncio.sleep(2)
            except Exception:
                pass
                
            # Wait for the API response to be intercepted
            for _ in range(25):
                if captured_data["status"] == "success":
                    break
                await asyncio.sleep(1)
            
            await browser.close()
            return captured_data
            
    except Exception as e:
        print(traceback.format_exc())
        return {"status": "failed", "error": f"Backend Error: {str(e)}", "hotels": []}
