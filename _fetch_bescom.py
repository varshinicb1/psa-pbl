import ssl, json, urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Try to find actual download URLs for BESCOM data
urls = [
    "https://data.opencity.in/api/3/action/package_show?id=bescom-data",
    "https://data.opencity.in/api/3/action/package_show?id=bescom-consumption-data",
    "https://data.opencity.in/api/3/action/package_show?id=bescom-high-tension-ht-lines-data",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        data = json.loads(resp.read())
        if data.get("success"):
            result = data["result"]
            print(f"\n=== {result.get('title', url)} ===")
            for r in result.get("resources", []):
                print(f"  {r.get('name','?')} | {r.get('format','?')} | {r.get('id','?')}")
                dl_url = r.get("url") or r.get("download_url")
                if dl_url:
                    print(f"    Download: {dl_url}")
        else:
            print(f"Failed: {url}")
    except Exception as e:
        print(f"Error {url}: {e}")
