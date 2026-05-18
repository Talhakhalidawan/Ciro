# 🌪️ CIRO — Real-Time Crisis & Weather Monitoring Server

CIRO is a premium, high-performance, and resilient Django-based emergency monitoring and intelligence backend. It acts as a safety sentinel for citizens in Pakistan, detecting climate spikes, hazardous wildfires, and severe road incidents, verifying them in real-time through social media data mining, and delivering actionable localized alerts.

```
                  ┌────────────────────────────────────────────────┐
                  │          Mobile App / Client Requests          │
                  └───────────────────────┬────────────────────────┘
                                          │ POST /api/weather/
                                          ▼
                  ┌────────────────────────────────────────────────┐
                  │          Concurrent Fetching Engine            │
                  │  (Weather, AQI, NASA FIRMS, TomTom Traffic)    │
                  └───────────────────────┬────────────────────────┘
                                          │ 
                                          ▼
                  ┌────────────────────────────────────────────────┐
                  │           Crisis & Anomaly Detection           │
                  │        (Temp Spikes, Hotspots, Hazards)        │
                  └───────────────────────┬────────────────────────┘
                                          │ Anomaly Triggered!
                                          ▼
                  ┌────────────────────────────────────────────────┐
                  │          Smart Multi-Platform Search           │
                  │   (YouTube, TikTok, Facebook, Twitter/X early) │
                  └───────────────────────┬────────────────────────┘
                                          │ Raw Social Data
                                          ▼
                  ┌────────────────────────────────────────────────┐
                  │    Python Relevance Scoring & Capping Engine   │
                  │       (Token Quota Optimization — Capped 7)    │
                  └───────────────────────┬────────────────────────┘
                                          │ Ultra-Lean JSON Prompt (Titles Only)
                                          ▼
                  ┌────────────────────────────────────────────────┐
                  │          Resilient AI Routing Engine           │
                  │       (Gemini-First, Groq, BluesMinds fallback)│
                  └───────────────────────┬────────────────────────┘
                                          │ Actionable Crisis Decision
                                          ▼
                  ┌────────────────────────────────────────────────┐
                  │            Re-hydration & Mapped Response      │
                  │      (Full Clickable URLs & Safety Helplines)  │
                  └────────────────────────────────────────────────┘
```

---

## ✨ Core Engineering Features

### ⚡ 1. Concurrent Environmental Engine
* Queries **Open-Meteo Climate API**, **Open-Meteo Air Quality Index (AQI)**, **NASA FIRMS (Thermal Hotspots)**, and **TomTom (Road & Traffic Incidents)** in parallel using a thread-pool (`ThreadPoolExecutor`).
* Slashes server-side intelligence assembly latency from 6+ seconds down to **under 1.5 seconds**.

### 📉 2. Token-Saving Programmatic Relevance Filter
* Scores all retrieved search result items locally in Python using a custom matching index of Pakistani crisis terms (e.g. `garmi`, `sylab`, `baarish`, `flood`, `wildfire`, `road closed`).
* Filters out unrelated noise and caps candidate list to the **top 7 most relevant items**.
* Strips all URLs and descriptions from the AI prompt, sending **ONLY** `id`, `platform`, and `title` to the LLM. 
* **Reduces LLM input token consumption by >80%**, saving massive API quota and preventing rate limit blocks!

### 🔌 3. Resilient AI Fallback & Failure Bypass
* **Gemini-First Routing**: Prioritizes `gemini-2.5-flash` for blazing-fast responses (~1s) and high rate limits, with sequential automatic fallbacks to **Groq**, **BluesMinds**, and **Mistral** on error.
* **Network Error Bypass**: Catches Brave/DuckDuckGo connectivity blocks (e.g. `ConnectError` on `site:x.com`) and aborts search queries for the affected platform early. Prevents long retry blocks and saves up to **4 seconds** per request.

### 📞 4. Dynamic Emergency Directory mapping
* Translates local safety advice into standardized emergency contacts dynamically without model hallucinations:
  * **Rescue 1122** — `1122`
  * **Police Emergency** — `15`
  * **Edhi Ambulance** — `115`
  * **Fire Brigade** — `16`
  * **NDMA** — `051-111-157-157`
  * **KP Tourism Helpline** — `1422`

---

## 🛠️ Installation & Setup

### 1. Clone the Project & Install Dependencies
Ensure you have Python 3.10+ installed:
```bash
pip install django django-cors-headers requests python-dotenv groq google-generativeai openai mistralai duckduckgo_search
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
# AI Models Keys
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
BLUESMINDS_API_KEY=your_bluesminds_key
MISTRAL_API_KEY=your_mistral_key

# External Services
MYTOOMTOM_API_KEY=4MuDCczkS9pTdYD9IyB4oVhw9jVyeIXo
```

### 3. Initialize Database Migrations
Create the SQLite database and generate state structures:
```bash
python manage.py makemigrations api
python manage.py migrate
```

### 4. Run the Dev Server
The CIRO mobile client integrates by default on port `9000`:
```bash
python manage.py runserver 9000
```

---

## 🛰️ API Documentation

### `POST /api/weather/`
Receives current coordinate tracking from mobile users and analyzes the situation for emergency conditions.

#### Request Payload
```json
{
  "latitude": 33.6844,
  "longitude": 73.0479,
  "time": "2026-05-18T12:00:00Z"
}
```

#### Response Payload (Anomaly Triggered - Compact & Mobile-Ready)
```json
{
  "status": "success",
  "environment": {
    "temperature_c": 46.0,
    "aqi": 80,
    "active_fires_nearby": 0
  },
  "traffic": {
    "incident_count": 0,
    "incidents": []
  },
  "alert": {
    "type": "heatwave",
    "severity": "high",
    "confidence": "high",
    "title": "Extreme Heatwave in Islamabad",
    "details": "Islamabad experienced a sharp temperature rise from 34.0°C to 46.0°C, indicating a severe heatwave.",
    "safety_advises": [
      "Stay hydrated and avoid direct sunlight during peak hours.",
      "Wear light, breathable clothing and use sunscreen."
    ],
    "help_resources": [
      "Rescue 1122 - 1122",
      "Pakistan Meteorological Department - 1170"
    ],
    "notification_details": {
      "type": "weather_alert",
      "title": "Heatwave Alert in Islamabad",
      "body": "Temperatures have surged to 46°C. Take precautions to stay safe."
    }
  },
  "top_posts": [
    {
      "platform": "tiktok",
      "query": "Islamabad sudden temperature rise 34 to 46 degrees",
      "items": [
        {
          "title": "46 Degrees Celsius | TikTok",
          "snippet": "154.1M posts. Discover videos related to 46 Degrees Celsius on TikTok.",
          "url": "https://www.tiktok.com/discover/46-degrees-celsius"
        }
      ]
    }
  ]
}
```

---

## 🧪 Testing Suite

We provide a comprehensive diagnostic and verification suite to validate all logic paths, triggers, and fallback mechanisms.

### 1. Diagnostic External Key Checker
Check the validity and connection states of your configured credentials:
```bash
python tests/test_external_apis.py
```

### 2. E2E Anomaly Integration Test
Executes four critical real-time scenarios (Heatwave rise, NASA FIRMS fire anomaly, TomTom road blockage hazard, and safe baseline response) targeting port `9000`:
```bash
python tests/test_api.py
```

All E2E scenarios verify:
* Database baseline transitions.
* Precise alert triggers, notifications, and localized helpline bindings.
* Compressed ID-post dynamic re-mapping and clickable verification link generation.