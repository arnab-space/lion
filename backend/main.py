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

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    target_url = f"https://www.ishoprewards.com/hotels/hotel-list?checkIn={checkin}&checkOut={checkout}&noOfRooms=1&city={city}&country=IN"
    
    async with async_playwright() as p:
        # Launching Chromium with flags optimized for free cloud tiers
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage"
            ] 
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
        
        await page.goto(target_url, wait_until="domcontentloaded")
        await asyncio.sleep(10) 
        
        await browser.close()
        return captured_data
