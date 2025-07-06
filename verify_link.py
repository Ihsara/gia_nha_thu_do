import requests

url = "https://aineistot.vayla.fi/?path=ava/Tie/Digiroad/Aineistojulkaisut/latest/Maakuntajako_digiroad_K/UUSIMAA.zip"
headers = {
    'Referer': 'https://aineistot.vayla.fi/spa/ava/Tie/Digiroad/Aineistojulkaisut/latest/'
}
try:
    response = requests.head(url, allow_redirects=True, timeout=15, headers=headers)
    print(f"URL: {url}")
    print(f"Status Code: {response.status_code}")
    print("Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
except requests.RequestException as e:
    print(f"An error occurred: {e}")
