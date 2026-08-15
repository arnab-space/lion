import json
import uuid
import httpx
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# List of all available proxy failovers from your dashboard
PROXY_POOL = [
    "http://zggsvjkj:fueqpv8tcjco@31.59.20.176:6754",
    "http://zggsvjkj:fueqpv8tcjco@31.56.127.193:7684",
    "http://zggsvjkj:fueqpv8tcjco@45.38.107.97:6014",
    "http://zggsvjkj:fueqpv8tcjco@198.105.121.200:6462"
]

@app.get("/")
async def root():
    return {"status": "online", "message": "High-Speed API Engine with Proxy Failover is running."}

@app.get("/scrape")
async def scrape_city(city: str, checkin: str, checkout: str):
    if city not in CITY_DATABASE:
        return {"status": "failed", "error": f"City '{city}' not found in database.", "hotels": []}
        
    data = CITY_DATABASE[city]
    
    payload = {
        "checkIn": checkin,
        "checkOut": checkout,
        "city": data.get("loc_name", city).strip(),
        "country": data.get("country", "IN").strip(),
        "state": data.get("state", "").strip(),
        "scr": "INR",
        "sct": "IN",
        "latitude": str(data.get("lat", "")),
        "longitude": str(data.get("lon", "")),
        "rooms": [{"room": "1", "numberOfAdults": "2", "numberOfChildren": "0", "childrenAge": ""}],
        "channel": "web",
        "pageNumber": 0,
        "noOfRooms": "1",
        "countryName": data.get("countryName", "India").strip(),
        "totalGuest": 2,
        "customerId": "",
        "numberOfRooms": 1,
        "cachedContent": True,
        "forNavigation": False,
        "locationSuggestion": {
            "id": str(data.get("loc_id", "")),
            "name": data.get("loc_name", city).strip(),
            "type": data.get("loc_type", "City").strip()
        }
    }
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://www.ishoprewards.com",
        "referer": "https://www.ishoprewards.com/hotels/hotel-list",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "x-booking-trace-id": str(uuid.uuid4())
    }

    # Loop through proxy pool until one succeeds or all fail
    for proxy_url in PROXY_POOL:
        try:
            print(f"Trying proxy: {proxy_url}")
            async with httpx.AsyncClient(proxy=proxy_url, verify=False, timeout=12.0) as client:
                await client.get("https://www.ishoprewards.com/", headers=headers, timeout=8.0)
                
                if "csrf-token" in client.cookies:
                    headers["csrf-token"] = client.cookies["csrf-token"]
                else:
                    headers["csrf-token"] = "645aac110e54595239ae07750ef04daadb800f4d3246ffd1062ecb652046822398dcd1975a6bca914bd475cfe752af62c5c06f9b0696e3bb6948b9c73daeca08ca6047193c5021dab961b7afdf2a5f6af41b36b7fd7ddd023fb1caf9ec64b1341055a8c4c36fc7e98c4530cf3bd42f99fbcf2d4003a464cb5a4da4846f445c6b"
                
                api_url = "https://www.ishoprewards.com/middleware/hotels/listing"
                response = await client.post(api_url, json=payload, headers=headers, timeout=15.0)
                
                if response.status_code == 200:
                    json_data = response.json()
                    if "response" in json_data and "hotels" in json_data["response"]:
                        return {"status": "success", "error": None, "hotels": json_data["response"]["hotels"]}
                else:
                    print(f"Proxy blocked with status {response.status_code}, trying next...")
        except Exception as e:
            print(f"Proxy {proxy_url} failed with error: {str(e)}, trying next...")
            continue
            
    return {"status": "failed", "error": "All proxy failovers exhausted. WAF blocked requests.", "hotels": []}
