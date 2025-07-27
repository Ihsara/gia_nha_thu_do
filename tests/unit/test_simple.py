#!/usr/bin/env python3

print("Starting simple test...")

try:
    print("Testing basic imports...")
    import json
    from datetime import datetime
    from typing import List, Dict
    from dataclasses import dataclass
    from enum import Enum
    print("✅ Basic imports successful")
    
    print("Testing loguru import...")
    from loguru import logger
    print("✅ Loguru import successful")
    
    print("Testing class definition...")
    class TestClass:
        def __init__(self):
            self.test = "working"
    
    test_instance = TestClass()
    print(f"✅ Class definition successful: {test_instance.test}")
    
    print("Testing enum definition...")
    class TestEnum(Enum):
        VALUE1 = "value1"
    
    print(f"✅ Enum definition successful: {TestEnum.VALUE1}")
    
    print("Testing dataclass definition...")
    @dataclass
    class TestDataClass:
        name: str
        value: int
    
    test_data = TestDataClass("test", 123)
    print(f"✅ Dataclass definition successful: {test_data}")
    
    print("All tests passed!")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()