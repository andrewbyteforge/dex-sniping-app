#!/usr/bin/env python3
"""
Simple API test to check if dashboard endpoints are working.

Run this while the dashboard is running to test the API endpoints.

File: api_test.py
Usage: python api_test.py
"""

import asyncio
import aiohttp
import json


async def test_dashboard_api():
    """Test the dashboard API endpoints."""
    print("🧪 Testing Dashboard API Endpoints")
    print("=" * 50)
    
    endpoints = [
        ("/", "Dashboard Home"),
        ("/api/stats", "Statistics"),
        ("/api/opportunities", "Opportunities"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint, description in endpoints:
            try:
                url = f"http://localhost:8000{endpoint}"
                print(f"\n🔍 Testing {description}: {url}")
                
                async with session.get(url) as response:
                    status = response.status
                    print(f"   Status: {status}")
                    
                    if status == 200:
                        if endpoint == "/":
                            # For HTML endpoint, just check if it contains expected content
                            text = await response.text()
                            if "Dashboard" in text or "DEX" in text:
                                print("   ✅ HTML content looks good")
                            else:
                                print("   ⚠️  HTML content may be incomplete")
                        else:
                            # For JSON endpoints
                            try:
                                data = await response.json()
                                print(f"   ✅ JSON Response: {type(data)}")
                                
                                if endpoint == "/api/opportunities":
                                    print(f"   📊 Opportunities count: {len(data) if isinstance(data, list) else 'not a list'}")
                                    if isinstance(data, list) and data:
                                        sample = data[0]
                                        print(f"   📝 Sample keys: {list(sample.keys()) if isinstance(sample, dict) else 'not a dict'}")
                                
                                elif endpoint == "/api/stats":
                                    print(f"   📈 Stats keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                                    if isinstance(data, dict):
                                        total_opps = data.get('total_opportunities', 'missing')
                                        print(f"   📊 Total opportunities: {total_opps}")
                                        
                            except json.JSONDecodeError as json_error:
                                print(f"   ❌ JSON decode error: {json_error}")
                                text = await response.text()
                                print(f"   📄 Raw response: {text[:200]}...")
                    else:
                        text = await response.text()
                        print(f"   ❌ Error: {text[:200]}...")
                        
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
    
    print("\n" + "=" * 50)
    print("🔧 If opportunities are not showing:")
    print("1. Check if the backend queue has opportunities")
    print("2. Verify the /api/opportunities endpoint returns data")
    print("3. Check browser console for JavaScript errors")
    print("4. Ensure WebSocket connection is working")


if __name__ == "__main__":
    """Entry point."""
    try:
        asyncio.run(test_dashboard_api())
    except Exception as e:
        print(f"❌ Test failed: {e}")