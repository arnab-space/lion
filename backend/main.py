import json
import urllib.parse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the database we just generated
with open('city_database.json', 'r') as f:
    CITY_DATABASE = json.load(f)

def generate_ishop_url(city_key, check_in, check_out):
    if city_key not in CITY_DATABASE:
        return None
        
    data = CITY_DATABASE[city_key]
    
    # URL encode fields that contain spaces and special characters
    state_encoded = urllib.parse.quote(data.get("state", ""))
    country_name_encoded = urllib.parse.quote(data.get("countryName", ""))
    loc_name_encoded = urllib.parse.quote(data.get("loc_name", ""))
    
    url = (
        f"https://www.ishoprewards.com/hotels/hotel-list?"
        f"checkIn={check_in}&checkOut={check_out}&noOfRooms=1"
        f"&city={urllib.parse.quote(data['city'])}&country={data['country']}&countryName={country_name_encoded}"
        f"&state={state_encoded}&scr=INR&sct=IN&room%5B0%5D=1"
        f"&numberOfAdults%5B0%5D=2&numberOfChildren%5B0%5D=0&childrenAge%5B0%5D="
        f"&channel=web&locationSuggestion.id={data['loc_id']}"
        f"&locationSuggestion.name={loc_name_encoded}&locationSuggestion.type={data['loc_type']}"
        f"&cachedContent=true&latitude={data['lat']}&longitude={data['lon']}"
        f"&numberOfRooms=1&totalGuest=2&selectedAges="
    )
    return url

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    target_url = generate_ishop_url(city, checkin, checkout)
    
    if not target_url:
        return {"status": "failed", "error": f"City '{city}' not found in database.", "hotels": []}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"] 
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        captured_data = {"status": "failed", "hotels": []}
        
        async def handle_response(response):
            if "listing" in response.url.lower() and response.request.method == "POST":
                try:
                    json_data = await response.json()
                    if "response" in json_data and "hotels" in json_data["response"]:
                        captured_data["status"] = "success"
                        captured_data["hotels"] = json_data["response"]["hotels"]
                except Exception:
                    pass

        page.on("response", handle_response)
        
        # Navigate directly to the fully constructed URL
        await page.goto(target_url, wait_until="domcontentloaded")
        await asyncio.sleep(10) # Wait for the POST request to trigger and be captured
        
        await browser.close()
        return captured_data
