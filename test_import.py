#!/usr/bin/env python3
"""Test import of data governance module."""

try:
    print("Attempting to import module...")
    import oikotie.automation.data_governance as dg
    print("Module imported successfully")
    
    print("Module contents:", dir(dg))
    
    print("Attempting to import DataGovernanceManager...")
    from oikotie.automation.data_governance import DataGovernanceManager
    print("DataGovernanceManager imported successfully")
    
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()