"""
Validation Testing Package

Progressive validation tests for the Oikotie spatial data processing system.
Implements the 3-step validation strategy: 10 samples → postal code → full Helsinki.

Test Structure:
- test_10_samples.py: Initial proof of concept with 10 listings
- test_postal_code.py: Medium scale validation with representative postal code
- test_full_helsinki.py: Complete dataset validation
- test_package_imports.py: Package import validation
"""

__all__ = [
    'test_10_samples',
    'test_postal_code', 
    'test_full_helsinki',
    'test_package_imports'
]
