import urllib.request
import json
import re
import sys

def get_countries():
    # Fetch country data
    url = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get_jobs_by_country():
    # Fetch companies offering relocation from markdown
    url = "https://raw.githubusercontent.com/AndrewStetsenko/tech-jobs-with-relocation/main/README.md"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        md = resp.read().decode()
    
    # Simple regex to parse Markdown list of countries and companies
    # e.g. ### 🇩🇪 Germany
    # - [Company](link)
    
    country_companies = {}
    current_country = None
    
    for line in md.split('\n'):
        line = line.strip()
        if line.startswith('### '):
            # Extract country name, ignoring emojis
            parts = line.replace('###', '').strip().split(' ')
            current_country = parts[-1] if len(parts) > 1 else parts[0]
            country_companies[current_country] = []
        elif line.startswith('- [') and current_country:
            match = re.search(r'\[(.*?)\]', line)
            if match:
                country_companies[current_country].append(match.group(1))
                
    return country_companies

def main(target_region, min_population):
    print("Loading data...")
    countries = get_countries()
    jobs = get_jobs_by_country()
    
    # Filter countries
    matched_countries = []
    for c in countries:
        name = c['name']['common']
        region = c.get('region', '')
        pop = c.get('population', 0)
        
        if region == target_region and pop >= min_population:
            # Check if there are jobs
            if name in jobs and len(jobs[name]) > 0:
                matched_countries.append({
                    'name': name,
                    'companies': jobs[name]
                })
                
    print(f"\nFound {len(matched_countries)} countries in {target_region} matching criteria with relocation jobs:\n")
    for mc in matched_countries:
        comps = mc['companies']
        print(f"=== {mc['name']} ===")
        print(f"Companies with relocation: {len(comps)}")
        print(f"Examples: {', '.join(comps[:5])}...\n")

if __name__ == "__main__":
    region = sys.argv[1] if len(sys.argv) > 1 else "Europe"
    min_pop = int(sys.argv[2]) if len(sys.argv) > 2 else 5000000
    main(region, min_pop)
