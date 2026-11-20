import urllib.request
import json

def get_countries_by_region(region="Europe"):
    url = f"https://restcountries.com/v3.1/region/{region}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def print_summary(countries, max_results=5):
    print(f"Found {len(countries)} countries. Top {max_results}:")
    for c in sorted(countries, key=lambda x: x.get('population', 0), reverse=True)[:max_results]:
        name = c['name']['common']
        pop = c.get('population', 0)
        langs = ", ".join(c.get('languages', {}).values())
        print(f"- {name}: population {pop:,}, languages: {langs}")

if __name__ == "__main__":
    data = get_countries_by_region("Europe")
    print_summary(data)
