#!/usr/bin/env python3
"""
Test script for VISA MCP Server.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pyvisa

async def test_visa_resources():
    """Test VISA resource listing."""
    print("Testing VISA resource listing...")
    
    try:
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        
        print(f"Found {len(resources)} VISA resources:")
        for i, resource in enumerate(resources, 1):
            print(f"  {i}. {resource}")
            
        # Test opening a resource (if available)
        if resources:
            test_resource = resources[0]
            print(f"\nTesting connection to: {test_resource}")
            
            try:
                instr = rm.open_resource(test_resource, timeout=1000)
                print(f"✓ Successfully opened {test_resource}")
                
                # Try a simple query if it looks like an instrument
                if test_resource.startswith('TCPIP') or 'INSTR' in test_resource:
                    try:
                        response = instr.query("*IDN?", timeout=1000)
                        print(f"✓ *IDN? response: {response.strip()}")
                    except Exception as e:
                        print(f"⚠ *IDN? query failed: {e}")
                
                instr.close()
                print(f"✓ Closed connection to {test_resource}")
                
            except Exception as e:
                print(f"✗ Failed to connect to {test_resource}: {e}")
        else:
            print("No VISA resources found for testing.")
            
    except Exception as e:
        print(f"Error: {e}")
        return False
        
    return True

async def main():
    """Main test function."""
    print("VISA MCP Server Test")
    print("=" * 40)
    
    success = await test_visa_resources()
    
    print("\n" + "=" * 40)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
