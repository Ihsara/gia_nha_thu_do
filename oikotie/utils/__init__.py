"""
Oikotie utilities package
Contains utility functions and classes for spatial processing, data analysis, and validation
"""

import re
from .enhanced_spatial_matching import EnhancedSpatialMatcher

def extract_postal_code(address):
    """Extract postal code from address string."""
    if not isinstance(address, str): 
        return None
    match = re.search(r'\b(\d{5})\b', address)
    return match.group(1) if match else None

__all__ = ['EnhancedSpatialMatcher', 'extract_postal_code']
