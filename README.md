============================================================
      CIRO WEATHER API — FULL TEST SUITE
    ============================================================
    
    ============================================================
    TEST 1 — WEATHER HEATWAVE ANOMALY
    ============================================================
    
      Step 1: Baseline (34°C, Islamabad)
      ✅ Baseline saved. Temp=34.0°C
    
      Step 2: Anomaly (46°C — rise of +12°C triggers alert)
      HTTP 200
      Environment: temp=46.0°C | aqi=80 | fires=0
      Traffic: 0 incident(s)
    
      🚨 ALERT TRIGGERED!
         type      : heatwave
         severity  : high
         confidence: high
         title     : Extreme Heatwave in Islamabad
         details   : Islamabad experienced a sharp temperature rise from 34.0°C to 46.0°C, indicating a severe heatwave.
         safety    : ['Stay hydrated and avoid direct sunlight during peak hours.', 'Wear light, breathable clothing and use sunscreen.']
         helplines : ['Rescue 1122 - 1122', 'Pakistan Meteorological Department - 1170']
         push notif: [weather_alert] Heatwave Alert in Islamabad — Temperatures have surged to 46°C. Take precautions to stay safe.
    
      📰 TOP POSTS (1):
         [tiktok] query='Islamabad sudden temperature rise 34 to 46 degrees'
           • 46 Degrees Celsius | TikTok
             Link: https://www.tiktok.com/discover/46-degrees-celsius
           • 154.1M posts. Discover videos related to 115 Degrees Hot on TikTok.
             Link: https://www.tiktok.com/discover/115-degrees-hot
    
    ============================================================
    TEST 2 — NASA FIRMS THERMAL ANOMALY (FIRE)
    ============================================================
    
      Step 1: Baseline (no fires)
      HTTP 200
    
      Step 2: 5 active fire hotspots detected
      HTTP 200
      Environment: temp=30.0°C | aqi=145 | fires=5
      Traffic: 0 incident(s)
    
      🚨 ALERT TRIGGERED!
         type      : wildfire
         severity  : high
         confidence: high
         title     : Wildfire Detected in Margalla Hills, Islamabad
         details   : NASA FIRMS detected 5 active thermal anomalies indicating potential wildfires in Margalla Hills.
         safety    : ['Avoid visiting Margalla Hills until the situation is under control.', 'Stay indoors if smoke or ash is visible in your area.']
         helplines : ['Rescue 1122 - 1122', 'Fire Brigade - 16']
         push notif: [fire_alert] Wildfire Alert in Margalla Hills — Active wildfires detected in Margalla Hills. Avoid the area and follow safety guidelines.
      📰 top_posts: [] (no relevant social posts found)
    
    ============================================================
    TEST 3 — TOMTOM ROAD INCIDENTS
    ============================================================
    
      Step 1: Baseline (no road incidents)
      HTTP 200
    
      Step 2: Road closed + accident
      HTTP 200
      Environment: temp=30.0°C | aqi=145 | fires=0
      Traffic: 2 incident(s)
    
      🚨 ALERT TRIGGERED!
         type      : flood
         severity  : high
         confidence: high
         title     : Severe Flooding in Islamabad
         details   : Heavy rainfall has caused road closures and flooding in multiple areas of Islamabad.
         safety    : ['Avoid traveling on flooded roads.', 'Stay indoors and monitor local weather updates.']
         helplines : ['Rescue 1122 - 1122']
         push notif: [weather_alert] Flood Alert in Islamabad — Severe flooding reported in G-10, G-9, and IJP Road areas. Avoid travel if possible.
    
      📰 TOP POSTS (1):
         [youtube] query='Islamabad road closed flooding today'
           • LIVE: Severe Stormy Rains in Islamabad | Roads Flooded - YouTube
             Link: https://www.youtube.com/watch?v=1if8CkfYvww
           • LIVE: Flooding in Islamabad and Rawalpindi | Islamabad rain today
             Link: https://www.youtube.com/watch?v=4aRmZQixSgk
    
    ============================================================
    TEST 4 — SAFE RESPONSE (no anomaly)
    ============================================================
      HTTP 200
      Environment: temp=36.3°C | aqi=145 | fires=0
      Traffic: 0 incident(s)
      ✅ No crisis — safe response returned.
      ✅ Response shape is correct (environment + traffic, no alert)
    
    ============================================================
      Done.
   