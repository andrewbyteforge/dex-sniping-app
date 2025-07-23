# solana_diagnostics.py
"""
Enhanced diagnostics for Solana/Pump.fun API issues.
"""

import asyncio
import aiohttp
import json
from datetime import datetime

async def diagnose_solana_apis():
    """Comprehensive Solana API diagnostics."""
    print("🔍 SOLANA API DIAGNOSTICS")
    print("=" * 50)
    
    # Test multiple Solana endpoints
    endpoints_to_test = [
        {
            "name": "Pump.fun API",
            "url": "https://frontend-api.pump.fun/coins",
            "params": {"limit": 1}
        },
        {
            "name": "Solana RPC", 
            "url": "https://api.mainnet-beta.solana.com",
            "method": "POST",
            "data": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getHealth"
            }
        },
        {
            "name": "Jupiter API",
            "url": "https://quote-api.jup.ag/v6/quote",
            "params": {
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 
                "amount": "100000000"
            }
        },
        {
            "name": "Birdeye API",
            "url": "https://public-api.birdeye.so/public/tokenlist",
            "params": {"sort_by": "v24hUSD", "sort_type": "desc", "offset": 0, "limit": 1}
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints_to_test:
            await test_endpoint(session, endpoint)
            print()

async def test_endpoint(session, endpoint_config):
    """Test a specific endpoint and provide detailed diagnostics."""
    name = endpoint_config["name"]
    url = endpoint_config["url"]
    
    print(f"🔗 Testing {name}")
    print(f"   URL: {url}")
    
    try:
        start_time = datetime.now()
        
        if endpoint_config.get("method") == "POST":
            # POST request (for Solana RPC)
            async with session.post(
                url, 
                json=endpoint_config["data"],
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                await process_response(response, start_time, name)
        else:
            # GET request
            params = endpoint_config.get("params", {})
            async with session.get(
                url, 
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                await process_response(response, start_time, name)
                
    except asyncio.TimeoutError:
        print(f"   ❌ TIMEOUT: {name} took longer than 10 seconds")
    except aiohttp.ClientError as e:
        print(f"   ❌ CONNECTION ERROR: {e}")
    except Exception as e:
        print(f"   ❌ UNKNOWN ERROR: {e}")

async def process_response(response, start_time, name):
    """Process and analyze the API response."""
    end_time = datetime.now()
    response_time = (end_time - start_time).total_seconds()
    
    print(f"   📊 Status Code: {response.status}")
    print(f"   ⏱️  Response Time: {response_time:.2f}s")
    
    # Analyze status codes
    if response.status == 200:
        print(f"   ✅ SUCCESS: {name} is working properly")
        try:
            data = await response.json()
            if name == "Pump.fun API" and "coins" in data:
                print(f"   📈 Found {len(data['coins'])} coins in response")
            elif name == "Solana RPC":
                print(f"   🏥 Solana Health: {data.get('result', 'Unknown')}")
            elif name == "Jupiter API":
                print(f"   💱 Jupiter Quote: Available")
            elif name == "Birdeye API":
                print(f"   🐦 Birdeye Data: Available")
        except Exception as parse_error:
            print(f"   ⚠️  Response parsing failed: {parse_error}")
            
    elif response.status == 429:
        print(f"   ⚠️  RATE LIMITED: {name} is rejecting too many requests")
        print(f"   💡 Solution: Reduce request frequency")
        
    elif response.status == 502:
        print(f"   ⚠️  BAD GATEWAY: {name} server is having issues")
        print(f"   💡 Solution: Try alternative endpoints")
        
    elif response.status == 503:
        print(f"   ⚠️  SERVICE UNAVAILABLE: {name} is temporarily down")
        print(f"   💡 Solution: Wait and retry later")
        
    elif response.status == 530:
        print(f"   ⚠️  OVERLOADED: {name} cannot handle current traffic")
        print(f"   💡 Solution: Use alternative endpoints or retry with delays")
        
    elif response.status >= 500:
        print(f"   ❌ SERVER ERROR: {name} is experiencing internal issues")
        
    elif response.status >= 400:
        print(f"   ❌ CLIENT ERROR: Request format issue")
        
    # Get response headers for more info
    if 'retry-after' in response.headers:
        retry_after = response.headers['retry-after']
        print(f"   🔄 Retry After: {retry_after} seconds")
        
    if 'x-ratelimit-remaining' in response.headers:
        remaining = response.headers['x-ratelimit-remaining']
        print(f"   📊 Rate Limit Remaining: {remaining}")

async def test_alternative_solana_endpoints():
    """Test alternative Solana data sources."""
    print("\n🔄 TESTING ALTERNATIVE SOLANA ENDPOINTS")
    print("=" * 50)
    
    alternatives = [
        "https://solana-api.projectserum.com",
        "https://api.devnet.solana.com", 
        "https://rpc.ankr.com/solana",
        "https://solana.public-rpc.com"
    ]
    
    async with aiohttp.ClientSession() as session:
        for rpc_url in alternatives:
            print(f"🔗 Testing: {rpc_url}")
            try:
                health_check = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getHealth"
                }
                
                async with session.post(
                    rpc_url,
                    json=health_check,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get('result', 'Unknown')
                        print(f"   ✅ Status: {response.status} - Health: {result}")
                    else:
                        print(f"   ❌ Status: {response.status}")
                        
            except Exception as e:
                print(f"   ❌ Failed: {e}")
            print()

if __name__ == "__main__":
    async def main():
        await diagnose_solana_apis()
        await test_alternative_solana_endpoints()
        
        print("\n💡 RECOMMENDATIONS:")
        print("1. If Pump.fun shows 530: Wait 5-10 minutes, high traffic period")
        print("2. If Solana RPC fails: Use alternative RPC endpoints")  
        print("3. If all fail: Solana network may be experiencing issues")
        print("4. Check https://status.solana.com/ for official status")
    
    asyncio.run(main())