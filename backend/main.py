import os
import time
import asyncio
import json
import smtplib
import urllib.parse
import traceback
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from playwright.async_api import async_playwright
from datetime import datetime, timedelta

# ==========================================
# ⚙️ CONFIGURATION & DYNAMIC DATES
# ==========================================
today = datetime.now()
check_in_dt = today + timedelta(days=15)
check_out_dt = check_in_dt + timedelta(days=1) 

CHECK_IN = check_in_dt.strftime("%Y-%m-%d")
CHECK_OUT = check_out_dt.strftime("%Y-%m-%d")

CITIES_TO_SEARCH = [
    "Mumbai","Delhi","Bangalore","Hyderabad","Chennai","Jaipur","Udaipur","Pune","Kolkata","Varanasi",
    "Ahmedabad","Gurugram","Lonavala","Candolim","Indore","Mysore","Lucknow","Pondicherry","Kochi","Calangute",
    "Munnar","Puri","Ooty","Nashik","Wayanad","Bhubaneswar","Agra","Visakhapatnam","Mussoorie","Chandigarh",
    "Amritsar","Mahabaleshwar","Noida","Guwahati","Rishikesh","Coimbatore","Navi Mumbai","Panaji","Jodhpur","Dehradun",
    "Tirupati","Madurai","Dwarka","Nagpur","Thiruvananthapuram","Shimla","Kovalam","New Delhi","Baga","Havelock Island",
    "Patna","Mahabalipuram","Aurangabad","Kodaikanal","Ujjain","Hampi","Manali","Raipur","Ayodhya","Bhopal",
    "Shillong","Vrindavan","Shirdi","Goa","Surat","Ghaziabad","Varkala","Nainital","Darjeeling","Vadodara",
    "Mangalore","Madikeri","Benaulim","Kozhikode","Cavelossim","Gangtok","Thane","Port Blair","Jaisalmer","Utorda",
    "Mandrem","Rameswaram","Haridwar","Morjim","Srinagar","Sawai Madhopur","Canacona","Mount Abu","Yercaud","Udupi",
    "Ludhiana","Siliguri","Sakleshpur","Alibaug","Anjuna","Kanpur","Kolhapur","Vagator","Digha","Vijaywada",
    "Kumarakom","Panchgani","Ranchi","Daman","Rajkot","Alleppey","Betalbatim","Igatpuri","Bekal","Zirakpur",
    "Dharamshala","Pushkar","Bambolim","Neemrana","Kasauli","Rajpipla","Katra","Neil Island","Faridabad","Somnath",
    "Vijayawada","Chikmagalur","Prayagraj","Kumbhalgarh","Mohali","Varca","Gokarna","Kannur","Jamshedpur","Salem",
    "Sasan Gir","Trichy","Pachmarhi","Jalandhar","Jabalpur","Saputara","Gorakhpur","Kanyakumari","Nathdwara","Jammu",
    "Bhuj","Gwalior","Matheran","Guruvayur","Chikkamagaluru","Diu","Belagavi","Deoghar","Ganpatipule","Yelagiri",
    "Mandarmani","Ajmer","Arossim","Shivamogga","Hubli","Chapora","Gulmarg","Attappallam","Kota","Bikaner",
    "Agartala","Mathura","Dapoli","Alwar","Kollam","Bhimtal","Dalhousie","Durgavado","Bareilly","Dhikuli",
    "Arambol","Sariska","Leh","Durgapur","Cherrapunjee","Vellore","Colva","Rajahmundry","Tiruvannamalai","Virajpet",
    "Gurgaon","Thanjavur","Gandhinagar","Kanchipuram","Jamnagar","Thrissur","Mandarmoni","Bogmalo","Karjat","Sangavi",
    "Murdeshwar","Ganjam","Kundapura","Arpora","Saligao","Agonda","Bandipur","Junagadh","Baichanalli","Palakkad",
    "Davanagere","Nandi Hills","Majorda","Khajuraho","Kumbakonam","Meerut","Orchha","Vagamon","Lansdowne","Kalimpong",
    "Ghate Section","Jakkalli (N. Begur)","Khopoli","Solapur","Silchar","Pahalgam","Pelling","Kakinada","Haldwani","Badami",
    "Mangaluru","Mcleodganj","Kasol","Bir Billing","Auli","Munsiyari","Ranikhet","Chopta","Mukteshwar","Tirthan Valley",
    "Jibhi","Chitkul","Sangla","Spiti","Tawang","Ziro","Majuli","Jorhat","Tezpur","Konark",
    "Bundi","Chittorgarh","Ranakpur","Coonoor","Kotagiri","Thekkady","Athirappilly","Auroville","Coorg","Kabini"
]

CSV_HEADERS = [
    "hotel_name", "location", "star_rating", "amenities", "search_city", "check_in", "check_out", 
    "ct_hids", "cleartrip_per_night", "cleartrip_base_fare", "cleartrip_taxes_fees", "cleartrip_partner_discount",
    "makemytrip_per_night", "makemytrip_base_fare", "makemytrip_taxes_fees", "makemytrip_partner_discount",
    "yatra_per_night", "yatra_base_fare", "yatra_taxes_fees", "yatra_partner_discount",
    "tripsure_per_night", "tripsure_base_fare", "tripsure_taxes_fees", "tripsure_partner_discount"
]

# Load the city database
try:
    with open('city_database.json', 'r') as f:
        CITY_DATABASE = json.load(f)
except FileNotFoundError:
    print("❌ Fatal Error: city_database.json not found in repository.")
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

# ==========================================
# 🚀 THE HYBRID SCRAPING ENGINE
# ==========================================
async def run_hybrid_scraper():
    async with async_playwright() as p:
        print("🚀 Launching Headless Browser Engine for GitHub Actions...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--single-process", 
                "--no-zygote"
            ]
        )
        
        context_args = {
            "viewport": {"width": 1440, "height": 900},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        
        proxy_server = os.environ.get("PROXY_SERVER")
        if proxy_server:
            print("🌐 External proxy layer verified. Routing traffic to bypass WAF...")
            context_args["proxy"] = {"server": proxy_server}
            if os.environ.get("PROXY_USERNAME"):
                context_args["proxy"]["username"] = os.environ.get("PROXY_USERNAME")
            if os.environ.get("PROXY_PASSWORD"):
                context_args["proxy"]["password"] = os.environ.get("PROXY_PASSWORD")
        else:
            print("⚠️ WARNING: Running proxy-free. GitHub Actions IPs are frequently blocked by firewalls.")

        context = await browser.new_context(**context_args)
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        # ==========================================
        # 🔐 AUTOMATED CLOUD LOGIN SEQUENCE
        # ==========================================
        print("🔐 Authenticating session...")
        try:
            await page.goto("https://www.ishoprewards.com/login", wait_until="domcontentloaded")
            email = os.environ.get("ISHOP_EMAIL")
            password = os.environ.get("ISHOP_PASSWORD")
            
            if email and password:
                await page.fill('input[type="email"]', email)  
                await page.fill('input[type="password"]', password)
                await page.click('button[type="submit"]') 
                await asyncio.sleep(5) 
                print("✅ Session Authenticated.")
            else:
                print("⚠️ ISHOP_EMAIL or ISHOP_PASSWORD missing. Proceeding unauthenticated.")
        except Exception as e:
            print(f"Login automation warning: {e}")

        all_results_parsed = []
        all_results_raw_dump = {}

        for city in CITIES_TO_SEARCH:
            print(f"\n🌍 Processing: {city}...")
            
            target_url = generate_ishop_url(city, CHECK_IN, CHECK_OUT)
            if not target_url:
                print(f"⚠️ {city} not found in database. Skipping.")
                continue
                
            captured_json = None
            
            async def handle_response(response):
                nonlocal captured_json
                if "listing" in response.url.lower() and response.request.method == "POST":
                    try:
                        json_data = await response.json()
                        if "response" in json_data and "hotels" in json_data["response"]:
                            captured_json = json_data
                    except Exception:
                        pass

            page.on("response", handle_response)
            
            try:
                await page.goto(target_url, wait_until="domcontentloaded")
                await asyncio.sleep(15) 
            except Exception as e:
                print(f"❌ Navigation failed for {city}: {e}")
                
            page.remove_listener("response", handle_response)

            if captured_json is None:
                print(f"⚠️ Warning: Telemetry engine bypassed extraction for {city}.")
                continue

            all_results_raw_dump[city] = captured_json
            hotel_list = captured_json["response"]["hotels"]
            print(f"📦 Intercept complete. Processing {len(hotel_list)} properties.")

            for hotel in hotel_list:
                row = {key: "N/A" for key in CSV_HEADERS}
                info = hotel.get("hotelInfo", {})
                row["hotel_name"] = info.get("name", "Unknown")
                row["location"] = info.get("address", "Unknown")
                row["star_rating"] = info.get("starRating", "N/A")
                row["search_city"] = city
                row["check_in"] = CHECK_IN
                row["check_out"] = CHECK_OUT
                
                facilities = info.get("facilities", [])
                if facilities:
                    row["amenities"] = ", ".join(facilities)

                price_summary = hotel.get("priceSummary", [])
                for sup in price_summary:
                    sup_name = sup.get("partnerName", "").lower()
                    prefix = ""
                    
                    if "cleartrip" in sup_name: 
                        prefix = "cleartrip"
                        row["ct_hids"] = sup.get("hotelId", "N/A")
                    elif "makemytrip" in sup_name or "mmt" in sup_name: prefix = "makemytrip"
                    elif "yatra" in sup_name: prefix = "yatra"
                    elif "tripsure" in sup_name: prefix = "tripsure"

                    if prefix:
                        row[f"{prefix}_per_night"] = sup.get("price", "N/A")
                        row[f"{prefix}_base_fare"] = sup.get("baseFare", "N/A")
                        row[f"{prefix}_taxes_fees"] = sup.get("tax", "N/A")
                        row[f"{prefix}_partner_discount"] = sup.get("discount", "N/A")
                        
                all_results_parsed.append(row)
            print(f"✅ Structural map completed for {city}.")

        await browser.close()

        # ==========================================
        # 💾 DOCUMENT ARCHIVE EXPORT
        # ==========================================
        timestamp = int(time.time())
        excel_filename = ""
        if all_results_parsed:
            excel_filename = f"ishop_export_parsed_{timestamp}.xlsx"
            df = pd.DataFrame(all_results_parsed, columns=CSV_HEADERS)
            df.to_excel(excel_filename, index=False)

            parsed_json_filename = f"ishop_export_parsed_{timestamp}.json"
            with open(parsed_json_filename, mode='w', encoding='utf-8') as file:
                json.dump(all_results_parsed, file, ensure_ascii=False, indent=4)

        if all_results_raw_dump:
            raw_json_filename = f"ishop_export_RAW_DUMP_{timestamp}.json"
            with open(raw_json_filename, mode='w', encoding='utf-8') as file:
                json.dump(all_results_raw_dump, file, ensure_ascii=False, indent=4)
                
        return all_results_parsed, excel_filename

# ==========================================
# 📧 EXECUTIVE REVIEW TRANSIT LOGISTICS
# ==========================================
def zip_and_share(parsed_data, excel_filename):
    print("\n📧 Preparing executive report email delivery...")
    
    sender_email = os.environ.get("GMAIL_USER")
    sender_password = os.environ.get("GMAIL_APP_PASSWORD") 
    recipient_env = os.environ.get("RECIPIENT_EMAIL")

    if not all([sender_email, sender_password, recipient_env]):
        print("⚠️ Environment keys absent. Secure mailing configuration dropped.")
        return

    recipient_emails = [email.strip() for email in recipient_env.split(",") if email.strip()]

    # ---------------------------------------------------------
    # 🧠 DATA CLEANING & DASHBOARD LOGIC
    # ---------------------------------------------------------
    def clean_val(val):
        if val == "N/A" or val is None or str(val).strip() == "" or str(val).lower() == "nan": return None
        try: return float(val)
        except ValueError: return None

    total_records = len(parsed_data)
    ct_count, mmt_count, yatra_count, ts_count = 0, 0, 0, 0
    valid_delta_count = 0  
    ct_wins, ct_ties, ct_losses = 0, 0, 0
    total_delta_pct = 0

    buckets = {
        "CT_Better_20_plus": 0, "CT_Better_15_20": 0, "CT_Better_10_15": 0, "CT_Better_5_10": 0, "CT_Better_0_5": 0,
        "Parity": 0,
        "Comp_Better_0_5": 0, "Comp_Better_5_10": 0, "Comp_Better_10_15": 0, "Comp_Better_15_20": 0, "Comp_Better_20_plus": 0
    }

    for row in parsed_data:
        ct_price = clean_val(row.get("cleartrip_per_night"))
        mmt_price = clean_val(row.get("makemytrip_per_night"))
        yatra_price = clean_val(row.get("yatra_per_night"))
        ts_price = clean_val(row.get("tripsure_per_night"))

        if ct_price is not None: ct_count += 1
        if mmt_price is not None: mmt_count += 1
        if yatra_price is not None: yatra_count += 1
        if ts_price is not None: ts_count += 1

        if ct_price is not None:
            comp_prices = []
            if mmt_price is not None: comp_prices.append(mmt_price)
            if yatra_price is not None: comp_prices.append(yatra_price)
            if ts_price is not None: comp_prices.append(ts_price)

            if len(comp_prices) == 0:
                ct_wins += 1
            else:
                min_comp_price = min(comp_prices)
                valid_delta_count += 1

                if ct_price < min_comp_price: ct_wins += 1
                elif ct_price == min_comp_price: ct_ties += 1
                else: ct_losses += 1

                if min_comp_price > 0:
                    delta_pct = ((ct_price - min_comp_price) / min_comp_price) * 100
                    total_delta_pct += delta_pct

                    if delta_pct < -20: buckets["CT_Better_20_plus"] += 1
                    elif -20 <= delta_pct < -15: buckets["CT_Better_15_20"] += 1
                    elif -15 <= delta_pct < -10: buckets["CT_Better_10_15"] += 1
                    elif -10 <= delta_pct < -5: buckets["CT_Better_5_10"] += 1
                    elif -5 <= delta_pct < 0: buckets["CT_Better_0_5"] += 1
                    elif delta_pct == 0: buckets["Parity"] += 1
                    elif 0 < delta_pct <= 5: buckets["Comp_Better_0_5"] += 1
                    elif 5 < delta_pct <= 10: buckets["Comp_Better_5_10"] += 1
                    elif 10 < delta_pct <= 15: buckets["Comp_Better_10_15"] += 1
                    elif 15 < delta_pct <= 20: buckets["Comp_Better_15_20"] += 1
                    else: buckets["Comp_Better_20_plus"] += 1

    win_rate = (ct_wins / ct_count * 100) if ct_count > 0 else 0
    avg_delta = (total_delta_pct / valid_delta_count) if valid_delta_count > 0 else 0
    
    def pct(val): return f"{(val / valid_delta_count * 100):.1f}%" if valid_delta_count > 0 else "0%"

    # ---------------------------------------------------------
    # ✉️ MULTIPART EMAIL CONSTRUCTION
    # ---------------------------------------------------------
    msg = MIMEMultipart()
    msg["Subject"] = f"📊 Reward 360 Domestic Scraper Report: {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipient_emails)

    body_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&display=swap" rel="stylesheet">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: 'Sora', Arial, sans-serif;">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6; padding: 20px 0; font-family: 'Sora', Arial, sans-serif;">
        <tr>
          <td align="center">
            <table width="750" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 25px rgba(0,0,0,0.07); border: 1px solid #e5e7eb;">
              
              <!-- Header Section -->
              <tr>
                <td style="background: linear-gradient(135deg, #1A365D 0%, #2A4365 100%); padding: 30px 40px; border-bottom: 5px solid #FF6F2C;">
                  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-family: 'Sora', Arial, sans-serif;">
                    <tr>
                      <td style="padding-bottom: 20px;">
                        <div style="background-color: #ffffff; display: inline-block; padding: 8px 16px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                          <img src="https://upload.wikimedia.org/wikipedia/commons/a/ae/Cleartrip_Original.svg" alt="Cleartrip" height="24" style="display: block; border: 0;">
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td>
                        <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 700; opacity: 0.95;">Reward 360 Domestic Scraper Report</h1>
                        <p style="margin: 5px 0 0 0; color: #cbd5e1; font-size: 13px;">Pipeline Execution: {datetime.now().strftime('%Y-%m-%d %H:%M')} IST</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Greeting -->
              <tr>
                <td style="padding: 30px 40px 10px 40px;">
                  <p style="color: #1f2937; font-size: 16px; line-height: 1.6; margin: 0; font-family: 'Sora', Arial, sans-serif;">
                    Hi team,<br><br>
                    Please find the attached report on reward 360 (Ishop) for the {CHECK_IN} to {CHECK_OUT} dates across {len(CITIES_TO_SEARCH)} cities. 
                    Data N/A anomalies have been cleaned and parsed for the analysis below.
                  </p>
                </td>
              </tr>

              <!-- Summary Cards -->
              <tr>
                <td style="padding: 20px 40px;">
                  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="font-family: 'Sora', Arial, sans-serif;">
                    <tr>
                      <td width="23%" style="background-color: #f8fafc; border-radius: 6px; padding: 15px; text-align: center; border: 1px solid #e2e8f0;">
                        <div style="color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase;">Total Searched</div>
                        <div style="color: #1A365D; font-size: 24px; font-weight: 800; margin-top: 5px;">{total_records:,}</div>
                      </td>
                      <td width="2%"></td>
                      <td width="23%" style="background-color: #f8fafc; border-radius: 6px; padding: 15px; text-align: center; border: 1px solid #e2e8f0;">
                        <div style="color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase;">CT Available</div>
                        <div style="color: #1A365D; font-size: 24px; font-weight: 800; margin-top: 5px;">{ct_count:,}</div>
                      </td>
                      <td width="2%"></td>
                      <td width="23%" style="background-color: #ecfdf5; border-radius: 6px; padding: 15px; text-align: center; border: 1px solid #d1fae5;">
                        <div style="color: #065f46; font-size: 11px; font-weight: 700; text-transform: uppercase;">CT Win Rate</div>
                        <div style="color: #059669; font-size: 24px; font-weight: 800; margin-top: 5px;">{win_rate:.1f}%</div>
                      </td>
                      <td width="2%"></td>
                      <td width="23%" style="background-color: #fff7ed; border-radius: 6px; padding: 15px; text-align: center; border: 1px solid #ffedd5;">
                        <div style="color: #9a3412; font-size: 11px; font-weight: 700; text-transform: uppercase;">Avg Delta %</div>
                        <div style="color: #ea580c; font-size: 24px; font-weight: 800; margin-top: 5px;">{avg_delta:.1f}%</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Partner Wise Count -->
              <tr>
                <td style="padding: 10px 40px 20px 40px;">
                  <h3 style="color: #1A365D; font-size: 14px; font-weight: 700; margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 0.5px; font-family: 'Sora', Arial, sans-serif;">Partner Wise Hotel Capture</h3>
                  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="text-align: center; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; font-family: 'Sora', Arial, sans-serif;">
                    <tr style="background-color: #f8fafc; color: #475569; font-weight: 700;">
                      <td style="padding: 12px; border-right: 1px solid #e2e8f0;">Cleartrip</td>
                      <td style="padding: 12px; border-right: 1px solid #e2e8f0;">MakeMyTrip</td>
                      <td style="padding: 12px; border-right: 1px solid #e2e8f0;">Yatra</td>
                      <td style="padding: 12px;">Trip Sure</td>
                    </tr>
                    <tr style="color: #1f2937; font-weight: 600;">
                      <td style="padding: 12px; border-right: 1px solid #e2e8f0;">{ct_count:,}</td>
                      <td style="padding: 12px; border-right: 1px solid #e2e8f0;">{mmt_count:,}</td>
                      <td style="padding: 12px; border-right: 1px solid #e2e8f0;">{yatra_count:,}</td>
                      <td style="padding: 12px;">{ts_count:,}</td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Rate Bucket Dashboard -->
              <tr>
                <td style="padding: 10px 40px 30px 40px;">
                  <h3 style="color: #1A365D; font-size: 14px; font-weight: 700; margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 0.5px; font-family: 'Sora', Arial, sans-serif;">Distribution Across Rate Buckets</h3>
                  
                  <table width="100%" border="0" cellspacing="0" cellpadding="10" style="text-align: center; border: 1px solid #e2e8f0; border-collapse: collapse; font-family: 'Sora', Arial, sans-serif;">
                    <tr style="background-color: #f8fafc; color: #475569; font-size: 10px; font-weight: 700; text-transform: uppercase;">
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #10b981;">CT &gt;20%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #10b981;">CT 15-20%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #10b981;">CT 10-15%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #10b981;">CT 5-10%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #10b981;">CT 0-5%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #94a3b8;">PARITY</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #f97316;">COMP 0-5%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #f97316;">COMP 5-10%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #f97316;">COMP 10-15%</td>
                      <td style="border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-top: 3px solid #f97316;">COMP 15-20%</td>
                      <td style="border-bottom: 1px solid #e2e8f0; border-top: 3px solid #f97316;">COMP &gt;20%</td>
                    </tr>
                    
                    <tr style="font-size: 16px; font-weight: 700; background-color: #ffffff;">
                      <td style="border-right: 1px solid #e2e8f0; color: #059669; padding-top: 15px;">{buckets['CT_Better_20_plus']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #059669; padding-top: 15px;">{buckets['CT_Better_15_20']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #059669; padding-top: 15px;">{buckets['CT_Better_10_15']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #059669; padding-top: 15px;">{buckets['CT_Better_5_10']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #059669; padding-top: 15px;">{buckets['CT_Better_0_5']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #64748b; padding-top: 15px;">{buckets['Parity']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #ea580c; padding-top: 15px;">{buckets['Comp_Better_0_5']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #ea580c; padding-top: 15px;">{buckets['Comp_Better_5_10']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #ea580c; padding-top: 15px;">{buckets['Comp_Better_10_15']}</td>
                      <td style="border-right: 1px solid #e2e8f0; color: #ea580c; padding-top: 15px;">{buckets['Comp_Better_15_20']}</td>
                      <td style="color: #ea580c; padding-top: 15px;">{buckets['Comp_Better_20_plus']}</td>
                    </tr>

                    <tr style="background-color: #ffffff; color: #94a3b8; font-size: 11px;">
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['CT_Better_20_plus'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['CT_Better_15_20'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['CT_Better_10_15'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['CT_Better_5_10'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['CT_Better_0_5'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['Parity'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['Comp_Better_0_5'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['Comp_Better_5_10'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['Comp_Better_10_15'])}</td>
                      <td style="border-right: 1px solid #e2e8f0; padding-bottom: 15px;">{pct(buckets['Comp_Better_15_20'])}</td>
                      <td style="padding-bottom: 15px;">{pct(buckets['Comp_Better_20_plus'])}</td>
                    </tr>
                  </table>
                  
                  <p style="margin: 10px 0 0 0; color: #94a3b8; font-size: 11px; text-align: right; font-family: 'Sora', Arial, sans-serif;">*Delta calculation: (Cleartrip Final - Minimum Competitor Final) / Minimum Competitor Final</p>
                </td>
              </tr>

              <!-- Attachment Notification -->
              <tr>
                <td style="padding: 0 40px 30px 40px;">
                  <div style="background-color: #f8fafc; border-left: 4px solid #1A365D; padding: 15px; border-radius: 4px;">
                    <p style="margin: 0; color: #1e293b; font-size: 14px; font-weight: 700; font-family: 'Sora', Arial, sans-serif;">📎 Deliverable Attached</p>
                    <p style="margin: 5px 0 0 0; color: #475569; font-size: 14px; font-family: 'Sora', Arial, sans-serif;">The processed Excel master file has been attached directly for immediate review.</p>
                  </div>
                </td>
              </tr>

              <!-- Signature -->
              <tr>
                <td style="padding: 0 40px 35px 40px;">
                  <p style="color: #4b5563; font-size: 15px; margin: 0; border-top: 1px solid #e5e7eb; padding-top: 20px; font-family: 'Sora', Arial, sans-serif;">
                    Regards,<br>
                    <strong>Arnab Kumar Kar</strong><br>
                    <span style="color:#6b7280; font-size:13px;">Assistant Manager - B2B API</span>
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(body_content, "html"))

    # Attach the Excel file directly
    try:
        print(f"📎 Attaching {excel_filename} to email...")
        with open(excel_filename, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(excel_filename)}")
        msg.attach(part)
    except Exception as e:
        print(f"❌ Failed to attach file to email object: {e}")
        return

    # Send mail
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_emails, msg.as_string())
        print("✅ Dispatch routing successful. Email delivered with Excel attachment.")
    except Exception as e:
        print(f"❌ Core transmission layer crash exception: {e}")

if __name__ == "__main__":
    parsed_data, excel_filename = asyncio.run(run_hybrid_scraper())
    if parsed_data and excel_filename:
        zip_and_share(parsed_data, excel_filename)
