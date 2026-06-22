"""Download real BESCOM datasets from data.opencity.in."""
import ssl, csv, json, io, os, urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

data_dir = "C:\\Users\\varsh\\OneDrive\\Documents\\6THSEM\\PSA\\pbl\\platform\\dt-bescom\\data"
os.makedirs(data_dir, exist_ok=True)

datasets = {
    "bescom_substations.csv": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/3c779061-159d-40ee-bc07-92691d4eec70/download/9f945eb2-b531-4d5f-a096-b9d6ddd7b1d4.csv",
    "bescom_consumption.csv": "https://data.opencity.in/dataset/c2e70b7b-2af9-4223-ad49-f67f32d9366f/resource/addf1f15-7c90-44db-ab13-572aae08b0f1/download/70d066f8-2145-4b98-9e94-d7657b8a04a0.csv",
    "bescom_ht_lines_2023.csv": "https://data.opencity.in/dataset/b6bb6c50-19f7-49f9-8425-00f96fad7dd9/resource/61a564f1-1b4e-457d-9f63-9448c6ef13c8/download/9cce9046-a070-44ee-a85a-4868aa9e957c.csv",
    "bescom_energy_req.csv": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/a2cebd72-0a37-4e78-86a9-4c419a560e50/download/b56ecf68-a00d-4912-ad3b-7928bd3b7219.csv",
    "bescom_num_consumers.csv": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/f133d9c4-92b9-488b-bf1d-3c17425990cf/download/c180c1da-9684-4887-8d56-13a806b4953f.csv",
    "bescom_units_sold.csv": "https://data.opencity.in/dataset/1b90de58-1e06-4b2c-bd29-2261493036a1/resource/b0ee93ea-65b6-4523-a500-235dd5f73896/download/e5e600c4-5686-4ad6-9920-8d05a659d226.csv",
    "bescom_ht_lines_2022.csv": "https://data.opencity.in/dataset/b6bb6c50-19f7-49f9-8425-00f96fad7dd9/resource/c4c8d7fd-3ae9-4854-bfe7-e562993bb695/download/1b5e037f-ebed-4ae6-8662-ead525ea60da.csv",
}

for filename, url in datasets.items():
    filepath = os.path.join(data_dir, filename)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        content = resp.read()
        with open(filepath, "wb") as f:
            f.write(content)
        print(f"OK {filename} ({len(content)} bytes)")
    except Exception as e:
        print(f"FAIL {filename}: {e}")
