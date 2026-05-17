from ddgs import DDGS

query = "site:x.com gemini"

with DDGS() as ddgs:
    # timelimit='d' filters for the past 24 hours
    results = ddgs.text(
        query=query, 
        timelimit='d', 
        max_results=20
    )
    
    for result in results:
        print(f"Title: {result.get('title')}")
        print(f"URL: {result.get('href')}\n")