from ddgs import DDGS

query = "'weather' site:reddit.com"

with DDGS() as ddgs:
    results = ddgs.text(
        query=query, 
        timelimit='d', 
        max_results=20
    )
    
    for result in results:
        print(f"Title: {result.get('title')}")
        print(f"Description: {result.get('body')}")
        print(f"URL: {result.get('href')}\n")