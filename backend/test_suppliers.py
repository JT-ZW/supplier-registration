"""Test script to check suppliers in database."""
import asyncio
from app.db.supabase import db

async def main():
    try:
        result = await db.list_suppliers(page=1, page_size=10)
        print(f"Total suppliers: {result.get('total', 0)}")
        print(f"Suppliers returned: {len(result.get('items', []))}")
        
        if result.get('items'):
            print("\nSuppliers:")
            for supplier in result['items']:
                print(f"  - {supplier.get('company_name')} (ID: {supplier.get('id')})")
                print(f"    Status: {supplier.get('status')}")
                print(f"    Email: {supplier.get('email')}")
        else:
            print("\nNo suppliers found in database!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
