import re

def extract_postal_code(address):
    if not isinstance(address, str): return None
    match = re.search(r'\b(\d{5})\b', address)
    return match.group(1) if match else None
