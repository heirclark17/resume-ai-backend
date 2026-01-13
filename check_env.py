#!/usr/bin/env python3
"""
Check Railway Environment Variables
"""
import os

print("=" * 60)
print("  CHECKING RAILWAY ENVIRONMENT VARIABLES")
print("=" * 60)
print()

# Required environment variables
required_vars = [
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "ALLOWED_ORIGINS"
]

# Optional environment variables
optional_vars = [
    "TEST_MODE",
    "DEBUG",
    "PORT"
]

print("REQUIRED VARIABLES:")
print("-" * 60)
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive data
        if "KEY" in var or "URL" in var:
            display_value = value[:10] + "..." if len(value) > 10 else "***"
        else:
            display_value = value
        print(f"✓ {var:25} = {display_value}")
    else:
        print(f"✗ {var:25} = NOT SET (MISSING!)")

print()
print("OPTIONAL VARIABLES:")
print("-" * 60)
for var in optional_vars:
    value = os.getenv(var)
    if value:
        print(f"✓ {var:25} = {value}")
    else:
        print(f"- {var:25} = Not set (using default)")

print()
print("=" * 60)

# Check if we can initialize the services
print()
print("TESTING SERVICE INITIALIZATION:")
print("-" * 60)

try:
    from app.config import get_settings
    settings = get_settings()
    print(f"✓ Settings loaded")
    print(f"  - TEST_MODE: {settings.test_mode}")
    print(f"  - OPENAI_API_KEY: {'SET' if settings.openai_api_key else 'NOT SET'}")
    print(f"  - PERPLEXITY_API_KEY: {'SET' if settings.perplexity_api_key else 'NOT SET'}")
except Exception as e:
    print(f"✗ Settings load failed: {e}")

try:
    from app.services.openai_tailor import OpenAITailor
    tailor = OpenAITailor()
    print(f"✓ OpenAITailor initialized")
except Exception as e:
    print(f"✗ OpenAITailor init failed: {e}")

try:
    from app.services.perplexity_client import PerplexityClient
    perplexity = PerplexityClient()
    print(f"✓ PerplexityClient initialized")
except Exception as e:
    print(f"✗ PerplexityClient init failed: {e}")

print()
print("=" * 60)
print("  RECOMMENDATION:")
print("=" * 60)
print()

openai_key = os.getenv("OPENAI_API_KEY")
perplexity_key = os.getenv("PERPLEXITY_API_KEY")

if not openai_key or not perplexity_key:
    print("MISSING API KEYS - You have two options:")
    print()
    print("Option 1: Set API keys in Railway (recommended for production)")
    print("  1. Go to Railway dashboard")
    print("  2. Select your backend service")
    print("  3. Go to Variables tab")
    print("  4. Add these variables:")
    if not openai_key:
        print("     - OPENAI_API_KEY = your-openai-api-key")
    if not perplexity_key:
        print("     - PERPLEXITY_API_KEY = your-perplexity-api-key")
    print()
    print("Option 2: Enable TEST_MODE (recommended for testing)")
    print("  1. Go to Railway dashboard")
    print("  2. Select your backend service")
    print("  3. Go to Variables tab")
    print("  4. Add: TEST_MODE = true")
    print("  5. This will use mock data instead of real API calls")
else:
    print("✓ All API keys are set!")
    print()
    print("If you're still getting errors:")
    print("  1. Check that the API keys are valid")
    print("  2. Check Railway logs for specific error messages:")
    print("     railway logs --service backend")
    print("  3. Verify you have API credits available")

print()
print("=" * 60)
