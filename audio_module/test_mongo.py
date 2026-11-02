"""Быстрый тест подключения к MongoDB Atlas."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database.mongodb import mongodb


async def main():
    print("=" * 50)
    print("Test MongoDB Atlas connection")
    print("=" * 50)
    print(f"URI: {settings.MONGO_URI[:30]}...")
    print(f"Database: {settings.MONGO_DB_NAME}")
    print()

    await mongodb.connect()

    if not mongodb.is_connected:
        print("[FAIL] MongoDB NOT connected!")
        print()
        print("Possible fixes:")
        print("1. Check your IP is whitelisted in Atlas -> Network Access")
        print("2. Try standard connection string (not SRV):")
        print("   In Atlas -> Connect -> Drivers -> select 'mongodb' instead of 'mongodb+srv'")
        print("3. Check DNS: your network may block SRV lookups")
        return

    print("[OK] MongoDB connected!")

    # Test write
    test_doc = {
        "interview_id": "test-123",
        "speech_rate": {"speech_rate_wpm": 120.5},
        "created_at": "2026-04-23T12:00:00Z",
    }
    mongo_id = await mongodb.insert_audio_analysis(test_doc)
    print(f"[OK] Document written: _id={mongo_id}" if mongo_id else "[FAIL] Write error!")

    # Test read
    result = await mongodb.get_audio_analysis("test-123")
    print(f"[OK] Document read: wpm={result['speech_rate']['speech_rate_wpm']}" if result else "[FAIL] Read error!")

    # Cleanup
    if mongodb.audio_analysis:
        await mongodb.audio_analysis.delete_many({"interview_id": "test-123"})
        print("[OK] Test data cleaned")

    await mongodb.disconnect()
    print()
    print("[OK] All good! MongoDB is ready.")


if __name__ == "__main__":
    asyncio.run(main())
