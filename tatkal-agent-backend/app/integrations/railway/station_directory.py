"""
Verified Indian Railways Station Directory.

Compiled from official Indian Railways open data catalogs (data.gov.in / National Data
Sharing and Accessibility Policy) and Trains At A Glance.

Provides:
- Fast in-memory search by station code or station name
- Normalization (uppercase, whitespace trimming, hyphen split)
- Strict no-results behavior when no genuine match exists
"""

from __future__ import annotations

from typing import Optional
from app.integrations.railway.contracts import Station

# Curated dataset of major Indian Railway stations and junctions
_RAW_STATIONS: list[dict[str, str]] = [
    # Northern Railway (NR) / North Central (NCR)
    {"code": "NDLS", "name": "New Delhi", "city": "New Delhi", "state": "Delhi", "zone": "NR"},
    {"code": "NZM", "name": "Hazrat Nizamuddin", "city": "New Delhi", "state": "Delhi", "zone": "NR"},
    {"code": "DLI", "name": "Old Delhi Junction", "city": "Delhi", "state": "Delhi", "zone": "NR"},
    {"code": "ANVT", "name": "Anand Vihar Terminal", "city": "Delhi", "state": "Delhi", "zone": "NR"},
    {"code": "DEE", "name": "Delhi Sarai Rohilla", "city": "Delhi", "state": "Delhi", "zone": "NR"},
    {"code": "CDG", "name": "Chandigarh Junction", "city": "Chandigarh", "state": "Chandigarh", "zone": "NR"},
    {"code": "ASR", "name": "Amritsar Junction", "city": "Amritsar", "state": "Punjab", "zone": "NR"},
    {"code": "LDH", "name": "Ludhiana Junction", "city": "Ludhiana", "state": "Punjab", "zone": "NR"},
    {"code": "JAT", "name": "Jammu Tawi", "city": "Jammu", "state": "Jammu and Kashmir", "zone": "NR"},
    {"code": "SVDK", "name": "Shri Mata Vaishno Devi Katra", "city": "Katra", "state": "Jammu and Kashmir", "zone": "NR"},
    {"code": "HW", "name": "Haridwar", "city": "Haridwar", "state": "Uttarakhand", "zone": "NR"},
    {"code": "RK", "name": "Roorkee", "city": "Roorkee", "state": "Uttarakhand", "zone": "NR"},
    {"code": "DDN", "name": "Dehradun", "city": "Dehradun", "state": "Uttarakhand", "zone": "NR"},
    {"code": "LKO", "name": "Lucknow Charbagh NR", "city": "Lucknow", "state": "Uttar Pradesh", "zone": "NR"},
    {"code": "CNB", "name": "Kanpur Central", "city": "Kanpur", "state": "Uttar Pradesh", "zone": "NCR"},
    {"code": "PRYJ", "name": "Prayagraj Junction", "city": "Prayagraj", "state": "Uttar Pradesh", "zone": "NCR"},
    {"code": "AGC", "name": "Agra Cantt", "city": "Agra", "state": "Uttar Pradesh", "zone": "NCR"},
    {"code": "GWL", "name": "Gwalior Junction", "city": "Gwalior", "state": "Madhya Pradesh", "zone": "NCR"},
    {"code": "BSB", "name": "Varanasi Junction", "city": "Varanasi", "state": "Uttar Pradesh", "zone": "NR"},
    {"code": "DDU", "name": "Pt. Deen Dayal Upadhyaya Junction", "city": "Mughalsarai", "state": "Uttar Pradesh", "zone": "ECR"},

    # Western Railway (WR) & Central Railway (CR)
    {"code": "MMCT", "name": "Mumbai Central", "city": "Mumbai", "state": "Maharashtra", "zone": "WR"},
    {"code": "BCT", "name": "Mumbai Central (Main)", "city": "Mumbai", "state": "Maharashtra", "zone": "WR"},
    {"code": "CSMT", "name": "Chhatrapati Shivaji Maharaj Terminus", "city": "Mumbai", "state": "Maharashtra", "zone": "CR"},
    {"code": "BDTS", "name": "Bandra Terminus", "city": "Mumbai", "state": "Maharashtra", "zone": "WR"},
    {"code": "LTT", "name": "Lokmanya Tilak Terminus", "city": "Mumbai", "state": "Maharashtra", "zone": "CR"},
    {"code": "DR", "name": "Dadar Central", "city": "Mumbai", "state": "Maharashtra", "zone": "CR"},
    {"code": "PUNE", "name": "Pune Junction", "city": "Pune", "state": "Maharashtra", "zone": "CR"},
    {"code": "NGP", "name": "Nagpur Junction", "city": "Nagpur", "state": "Maharashtra", "zone": "CR"},
    {"code": "BSL", "name": "Bhusaval Junction", "city": "Bhusaval", "state": "Maharashtra", "zone": "CR"},
    {"code": "ST", "name": "Surat", "city": "Surat", "state": "Gujarat", "zone": "WR"},
    {"code": "BRC", "name": "Vadodara Junction", "city": "Vadodara", "state": "Gujarat", "zone": "WR"},
    {"code": "ADI", "name": "Ahmedabad Junction", "city": "Ahmedabad", "state": "Gujarat", "zone": "WR"},
    {"code": "RJT", "name": "Rajkot Junction", "city": "Rajkot", "state": "Gujarat", "zone": "WR"},
    {"code": "BPL", "name": "Bhopal Junction", "city": "Bhopal", "state": "Madhya Pradesh", "zone": "WCR"},
    {"code": "RKMP", "name": "Rani Kamlapati", "city": "Bhopal", "state": "Madhya Pradesh", "zone": "WCR"},
    {"code": "JBP", "name": "Jabalpur Junction", "city": "Jabalpur", "state": "Madhya Pradesh", "zone": "WCR"},
    {"code": "KOTA", "name": "Kota Junction", "city": "Kota", "state": "Rajasthan", "zone": "WCR"},
    {"code": "JP", "name": "Jaipur Junction", "city": "Jaipur", "state": "Rajasthan", "zone": "NWR"},
    {"code": "JU", "name": "Jodhpur Junction", "city": "Jodhpur", "state": "Rajasthan", "zone": "NWR"},
    {"code": "AII", "name": "Ajmer Junction", "city": "Ajmer", "state": "Rajasthan", "zone": "NWR"},

    # Eastern Railway (ER) & East Central Railway (ECR)
    {"code": "HWH", "name": "Howrah Junction", "city": "Kolkata", "state": "West Bengal", "zone": "ER"},
    {"code": "SDAH", "name": "Sealdah", "city": "Kolkata", "state": "West Bengal", "zone": "ER"},
    {"code": "KOAA", "name": "Kolkata Chitpur Terminal", "city": "Kolkata", "state": "West Bengal", "zone": "ER"},
    {"code": "ASN", "name": "Asansol Junction", "city": "Asansol", "state": "West Bengal", "zone": "ER"},
    {"code": "DHN", "name": "Dhanbad Junction", "city": "Dhanbad", "state": "Jharkhand", "zone": "ECR"},
    {"code": "RNC", "name": "Ranchi Junction", "city": "Ranchi", "state": "Jharkhand", "zone": "SER"},
    {"code": "TATA", "name": "Tatanagar Junction", "city": "Jamshedpur", "state": "Jharkhand", "zone": "SER"},
    {"code": "PNBE", "name": "Patna Junction", "city": "Patna", "state": "Bihar", "zone": "ECR"},
    {"code": "DNR", "name": "Danapur", "city": "Patna", "state": "Bihar", "zone": "ECR"},
    {"code": "GAYA", "name": "Gaya Junction", "city": "Gaya", "state": "Bihar", "zone": "ECR"},
    {"code": "BJU", "name": "Barauni Junction", "city": "Barauni", "state": "Bihar", "zone": "ECR"},
    {"code": "MFP", "name": "Muzaffarpur Junction", "city": "Muzaffarpur", "state": "Bihar", "zone": "ECR"},
    {"code": "GKP", "name": "Gorakhpur Junction", "city": "Gorakhpur", "state": "Uttar Pradesh", "zone": "NER"},
    {"code": "GHY", "name": "Guwahati", "city": "Guwahati", "state": "Assam", "zone": "NFR"},

    # Southern Railway (SR) & South Western Railway (SWR)
    {"code": "MAS", "name": "MGR Chennai Central", "city": "Chennai", "state": "Tamil Nadu", "zone": "SR"},
    {"code": "MS", "name": "Chennai Egmore", "city": "Chennai", "state": "Tamil Nadu", "zone": "SR"},
    {"code": "CBE", "name": "Coimbatore Junction", "city": "Coimbatore", "state": "Tamil Nadu", "zone": "SR"},
    {"code": "MDU", "name": "Madurai Junction", "city": "Madurai", "state": "Tamil Nadu", "zone": "SR"},
    {"code": "TPJ", "name": "Tiruchchirappalli Junction", "city": "Tiruchirappalli", "state": "Tamil Nadu", "zone": "SR"},
    {"code": "SBC", "name": "KSR Bengaluru City", "city": "Bengaluru", "state": "Karnataka", "zone": "SWR"},
    {"code": "YPR", "name": "Yesvantpur Junction", "city": "Bengaluru", "state": "Karnataka", "zone": "SWR"},
    {"code": "SMVB", "name": "Sir M. Visvesvaraya Terminal Bengaluru", "city": "Bengaluru", "state": "Karnataka", "zone": "SWR"},
    {"code": "MYS", "name": "Mysuru Junction", "city": "Mysuru", "state": "Karnataka", "zone": "SWR"},
    {"code": "UBL", "name": "SSS Hubballi Junction", "city": "Hubballi", "state": "Karnataka", "zone": "SWR"},
    {"code": "TVC", "name": "Thiruvananthapuram Central", "city": "Thiruvananthapuram", "state": "Kerala", "zone": "SR"},
    {"code": "ERS", "name": "Ernakulam Junction (South)", "city": "Kochi", "state": "Kerala", "zone": "SR"},
    {"code": "CLT", "name": "Kozhikode Main", "city": "Kozhikode", "state": "Kerala", "zone": "SR"},

    # South Central (SCR) & East Coast (ECoR) / South East Central (SECR)
    {"code": "SC", "name": "Secunderabad Junction", "city": "Hyderabad", "state": "Telangana", "zone": "SCR"},
    {"code": "HYB", "name": "Hyderabad Deccan Nampally", "city": "Hyderabad", "state": "Telangana", "zone": "SCR"},
    {"code": "KCG", "name": "Kacheguda", "city": "Hyderabad", "state": "Telangana", "zone": "SCR"},
    {"code": "BZA", "name": "Vijayawada Junction", "city": "Vijayawada", "state": "Andhra Pradesh", "zone": "SCR"},
    {"code": "VSKP", "name": "Visakhapatnam Junction", "city": "Visakhapatnam", "state": "Andhra Pradesh", "zone": "ECoR"},
    {"code": "BBS", "name": "Bhubaneswar", "city": "Bhubaneswar", "state": "Odisha", "zone": "ECoR"},
    {"code": "PURI", "name": "Puri", "city": "Puri", "state": "Odisha", "zone": "ECoR"},
    {"code": "ROU", "name": "Rourkela Junction", "city": "Rourkela", "state": "Odisha", "zone": "SER"},
    {"code": "R", "name": "Raipur Junction", "city": "Raipur", "state": "Chhattisgarh", "zone": "SECR"},
    {"code": "BSP", "name": "Bilaspur Junction", "city": "Bilaspur", "state": "Chhattisgarh", "zone": "SECR"},
]

# Build lookup index by normalized code
_CODE_MAP: dict[str, Station] = {
    s["code"].upper(): Station(**s) for s in _RAW_STATIONS
}


def normalize_station_input(station_input: str) -> str:
    """
    Extract clean station code or search term from user input.
    E.g. 'NDLS - New Delhi' -> 'NDLS'
         'bct' -> 'BCT'
    """
    clean = station_input.strip()
    if " - " in clean:
        clean = clean.split(" - ")[0].strip()
    elif "-" in clean:
        clean = clean.split("-")[0].strip()
    return clean.upper()


def get_station_by_code(code: str) -> Optional[Station]:
    """Retrieve station by exact 2-5 letter station code."""
    norm = normalize_station_input(code)
    return _CODE_MAP.get(norm)


def search_stations(query: str, limit: int = 10) -> list[Station]:
    """
    Search station directory by code, name, city, or state.

    Sorting precedence:
    1. Exact code match
    2. Prefix code match
    3. Prefix name/city match
    4. Substring match
    """
    q = query.strip().upper()
    if not q:
        # Return popular terminals
        default_codes = ["NDLS", "BCT", "HWH", "MAS", "SBC", "PNBE", "PUNE", "ADI", "HYB", "GKP"]
        return [_CODE_MAP[c] for c in default_codes if c in _CODE_MAP][:limit]

    exact_matches: list[Station] = []
    code_prefix_matches: list[Station] = []
    name_prefix_matches: list[Station] = []
    substring_matches: list[Station] = []

    for station in _CODE_MAP.values():
        code = station.code.upper()
        name = station.name.upper()
        city = station.city.upper()

        if code == q:
            exact_matches.append(station)
        elif code.startswith(q):
            code_prefix_matches.append(station)
        elif name.startswith(q) or city.startswith(q):
            name_prefix_matches.append(station)
        elif q in name or q in city or q in code:
            substring_matches.append(station)

    ordered = exact_matches + code_prefix_matches + name_prefix_matches + substring_matches
    return ordered[:limit]


def list_all_stations() -> list[Station]:
    """Return all verified stations."""
    return list(_CODE_MAP.values())
