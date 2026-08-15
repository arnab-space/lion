import json
import urllib.parse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import asyncio
import traceback

app = FastAPI()

# 1. FIXED CORS POLICY
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False, # Critical: Must be False when origin is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the city database on startup
try:
    with open('city_database.json', 'r') as f:
        CITY_DATABASE = json.load(f)
except FileNotFoundError:
    print("Warning: city_database.json not found.")
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
    return {"status": "online", "message": "iShop Scraper API is actively running."}

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    target_url = generate_ishop_url(city, checkin, checkout)
    
    if not target_url:
        return {"status": "failed", "error": f"City '{city}' not found in database.", "hotels": []}
    
    # 3. GRACEFUL CRASH HANDLER
    try:
        async with async_playwright() as p:
            # 2. MEMORY-SAVING CHROMIUM FLAGS
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-dev-shm-usage",
                    "--single-process", # Prevents OOM kills on Render's 512MB tier
                    "--no-zygote"
                ] 
            )
            context = await browser.new_context()
            page = await context.new_page()
            
            captured_data = {"status": "failed", "error": "No data intercepted. Try searching again.", "hotels": []}
            
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
            
            await page.goto(target_url, wait_until="domcontentloaded")
            await asyncio.sleep(12) 
            
            await browser.close()
            return captured_data
            
    except Exception as e:
        print(traceback.format_exc())
        return {"status": "failed", "error": f"Backend Error: {str(e)}", "hotels": []}
