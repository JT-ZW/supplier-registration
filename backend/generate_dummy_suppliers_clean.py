"""
Generate dummy supplier data for testing purposes.
Creates 200 suppliers across different categories, locations, and statuses.
"""

import asyncio
import random
from datetime import datetime, timedelta
from uuid import uuid4
from app.db.supabase import db


# Business categories
CATEGORIES = [
    "CONSTRUCTION",
    "MANUFACTURING", 
    "FOOD_BEVERAGE",
    "HEALTHCARE",
    "IT_SERVICES",
    "LOGISTICS",
    "CONSULTING",
    "CLEANING_SERVICES",
    "SECURITY_SERVICES",
    "GENERAL_SUPPLIES",
    "OTHER"
]

# Supplier statuses
STATUSES = [
    ("APPROVED", 0.50),      # 50% approved
    ("SUBMITTED", 0.20),     # 20% submitted
    ("UNDER_REVIEW", 0.15),  # 15% under review
    ("NEED_MORE_INFO", 0.08), # 8% need more info
    ("INCOMPLETE", 0.05),    # 5% incomplete
    ("REJECTED", 0.02),      # 2% rejected
]

# Zimbabwe locations (cities and provinces)
LOCATIONS = [
    ("Harare", "Harare CBD"),
    ("Harare", "Chitungwiza"),
    ("Harare", "Ruwa"),
    ("Harare", "Norton"),
    ("Bulawayo", "Bulawayo CBD"),
    ("Manicaland", "Mutare"),
    ("Manicaland", "Rusape"),
    ("Mashonaland East", "Marondera"),
    ("Mashonaland West", "Chinhoyi"),
    ("Mashonaland West", "Kadoma"),
    ("Masvingo", "Masvingo"),
    ("Midlands", "Gweru"),
    ("Midlands", "Kwekwe"),
    ("Matabeleland North", "Hwange"),
    ("Matabeleland North", "Victoria Falls"),
    ("Matabeleland South", "Gwanda"),
]

# Company name prefixes and suffixes
COMPANY_PREFIXES = [
    "Rainbow", "Sunrise", "Premier", "Elite", "Global", "National",
    "Universal", "Continental", "Supreme",  "Royal", "Imperial", "Capital",
    "Metro", "Excel", "Titan", "Pioneer", "Vertex", "Apex", "Summit",
    "Zenith", "Optimal", "Prime", "Prestige", "Dynamic", "Innovative"
]

COMPANY_TYPES = {
    "CONSTRUCTION": ["Builders", "Construction", "Engineering", "Contractors", "Projects"],
    "MANUFACTURING": ["Industries", "Manufacturing", "Producers", "Fabricators", "Works"],
    "FOOD_BEVERAGE": ["Foods", "Catering", "Supplies", "Provisions", "Beverages"],
    "HEALTHCARE": ["Medical", "Healthcare", "Clinic", "Pharmacy", "Health Services"],
    "IT_SERVICES": ["Technologies", "Software", "Systems", "IT Solutions", "Digital"],
    "LOGISTICS": ["Logistics", "Transport", "Freight", "Couriers", "Delivery"],
    "CONSULTING": ["Consultants", "Advisory", "Solutions", "Group", "Associates"],
    "CLEANING_SERVICES": ["Cleaning", "Hygiene", "Maintenance", "Services", "Facilities"],
    "SECURITY_SERVICES": ["Security", "Guards", "Protection", "SafeGuard", "Sentinel"],
    "GENERAL_SUPPLIES": ["Traders", "Suppliers", "Merchants", "Distributors", "Wholesale"],
    "OTHER": ["Enterprises", "Ventures", "Holdings", "Group", "Services"]
}

COMPANY_SUFFIXES = ["(Pvt) Ltd", "Limited", "Inc", "Enterprises", "Group", "& Co"]

# Contact person names
FIRST_NAMES = [
    "Tendai", "Tapiwa", "Chipo", "Rumbi", "Tinashe", "Nyasha", "Fungai",
    "Tafadzwa", "Tsitsi", "Rutendo", "Takudzwa", "Munashe", "Kudakwashe",
    "Blessing", "Grace", "Faith", "Hope", "Trust", "Wisdom", "Pride",
    "John", "Michael", "David", "James", "Robert", "Mary", "Patricia",
    "Linda", "Barbara", "Elizabeth", "William", "Richard", "Thomas"
]

LAST_NAMES = [
    "Moyo", "Ncube", "Dube", "Sibanda", "Ndlovu", "Mpofu", "Khumalo",
    "Nyathi", "Gumede", "Mthethwa", "Nkomo", "Banda", "Phiri", "Tembo",
    "Chikwamba", "Chitamba", "Mazvita", "Murungweni", "Mashingaidze",
    "Mutasa", "Chidziva", "Mapfumo", "Mavhunga", "Savanhu", "Musarurwa"
]


def generate_phone():
    """Generate realistic Zimbabwe phone number."""
    prefixes = ["0771", "0772", "0773", "0774", "0778", "0783", "0784", "0712", "0713", "0714"]
    return f"{random.choice(prefixes)} {random.randint(100, 999)} {random.randint(100, 999)}"


def generate_company_name(category):
    """Generate realistic company name based on category."""
    prefix = random.choice(COMPANY_PREFIXES)
    type_word = random.choice(COMPANY_TYPES[category])
    suffix = random.choice(COMPANY_SUFFIXES)
    return f"{prefix} {type_word} {suffix}"


def generate_contact_name():
    """Generate contact person name."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"


def generate_address(city):
    """Generate address."""
    street_numbers = random.randint(1, 999)
    street_names = ["Main", "Industrial", "Charter", "George Silundika", "Samora Machel",
                   "Robert Mugabe", "Nelson Mandela", "Julius Nyerere", "Kenneth Kaunda",
                   "Leopold Takawira", "Jason Moyo", "Josiah Tongogara"]
    street_types = ["Street", "Road", "Avenue", "Drive", "Way"]
    
    return f"{street_numbers} {random.choice(street_names)} {random.choice(street_types)}, {city}"


def get_status_distribution():
    """Get status based on weighted distribution."""
    rand = random.random()
    cumulative = 0
    for status, probability in STATUSES:
        cumulative += probability
        if rand <= cumulative:
            return status
    return "APPROVED"


def generate_registration_number():
    """Generate realistic registration number."""
    year = random.randint(2010, 2025)
    number = random.randint(10000, 99999)
    return f"REG/{year}/{number}"


def generate_tax_id():
    """Generate tax ID number."""
    return f"{random.randint(10000000, 99999999)}"


async def create_dummy_suppliers(count=200):
    """Create dummy supplier data."""
    print("=" * 80)
    print(f"CREATING {count} DUMMY SUPPLIERS")
    print("=" * 80)
    
    created_count = 0
    failed_count = 0
    
    for i in range(1, count + 1):
        try:
            # Generate supplier data
            category = random.choice(CATEGORIES)
            province, city = random.choice(LOCATIONS)
            status = get_status_distribution()
            company_name = generate_company_name(category)
            contact_name = generate_contact_name()
            
            # Generate dates based on status
            created_at = datetime.utcnow() - timedelta(days=random.randint(1, 365))
            
            submitted_at = None
            reviewed_at = None
            reviewed_by = None
            
            if status in ["SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED", "NEED_MORE_INFO"]:
                submitted_at = created_at + timedelta(days=random.randint(1, 7))
            
            if status in ["UNDER_REVIEW", "APPROVED", "REJECTED", "NEED_MORE_INFO"]:
                reviewed_at = submitted_at + timedelta(days=random.randint(1, 14)) if submitted_at else None
            
            # Create supplier record
            supplier_data = {
                "id": str(uuid4()),
                "email": f"dummy.supplier.{i:04d}@test.procurement.com",
                "company_name": company_name,
                "registration_number": generate_registration_number(),
                "business_category": category,
                "contact_person_name": contact_name,
                "contact_person_title": random.choice(["Managing Director", "General Manager", "CEO", "Director", "Operations Manager"]),
                "phone": generate_phone(),
                "street_address": generate_address(city),
                "city": city,
                "state_province": province,
                "country": "Zimbabwe",
                "postal_code": f"{random.randint(1000, 9999)}",
                "website": f"www.{company_name.lower().replace(' ', '').replace('(', '').replace(')', '').replace('&', 'and')[:30]}.co.zw" if random.random() > 0.3 else None,
                "years_in_business": random.randint(1, 25),
                "tax_id": generate_tax_id(),
                "status": status,
                "activity_status": "ACTIVE" if status == "APPROVED" else "INACTIVE",
                "created_at": created_at.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "submitted_at": submitted_at.isoformat() if submitted_at else None,
                "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
                "reviewed_by": reviewed_by
            }
            
            # Insert into database
            result = db._client.table("suppliers").insert(supplier_data).execute()
            
            if result.data:
                created_count += 1
                if i % 20 == 0:
                    print(f"   Progress: {i}/{count} suppliers created...")
            else:
                failed_count += 1
                print(f"   ✗ Failed to create supplier {i}")
                
        except Exception as e:
            failed_count += 1
            print(f"   ✗ Error creating supplier {i}: {str(e)}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total requested: {count}")
    print(f"Successfully created: {created_count}")
    print(f"Failed: {failed_count}")
    print(f"Success rate: {(created_count/count*100):.1f}%")
    
    # Show distribution
    print("\n" + "-" * 80)
    print("STATUS DISTRIBUTION")
    print("-" * 80)
    
    for status, expected_pct in STATUSES:
        result = db._client.table("suppliers")\
            .select("id", count="exact")\
            .like("email", "dummy.supplier.%@test.procurement.com")\
            .eq("status", status)\
            .execute()
        
        actual_count = result.count if result.count else 0
        actual_pct = (actual_count / created_count * 100) if created_count > 0 else 0
        print(f"   {status:20s}: {actual_count:3d} ({actual_pct:5.1f}% - expected {expected_pct*100:.0f}%)")
    
    print("\n" + "-" * 80)
    print("CATEGORY DISTRIBUTION")
    print("-" * 80)
    
    for category in CATEGORIES:
        result = db._client.table("suppliers")\
            .select("id", count="exact")\
            .like("email", "dummy.supplier.%@test.procurement.com")\
            .eq("business_category", category)\
            .execute()
        
        actual_count = result.count if result.count else 0
        print(f"   {category:25s}: {actual_count:3d}")
    
    print("\n" + "-" * 80)
    print("LOCATION DISTRIBUTION (Top 10)")
    print("-" * 80)
    
    city_counts = {}
    for province, city in LOCATIONS:
        result = db._client.table("suppliers")\
            .select("id", count="exact")\
            .like("email", "dummy.supplier.%@test.procurement.com")\
            .eq("city", city)\
            .execute()
        
        city_counts[city] = result.count if result.count else 0
    
    sorted_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for city, count in sorted_cities:
        print(f"   {city:25s}: {count:3d}")
    
    print("\n" + "=" * 80)
    print("✅ DUMMY DATA CREATION COMPLETE!")
    print("=" * 80)
    print(f"\nAll dummy suppliers are identifiable by:")
    print(f"  Email pattern: dummy.supplier.0001@test.procurement.com (to .{count:04d}@...)")
    print(f"\nTo delete this dummy data, run: python delete_dummy_data.py")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(create_dummy_suppliers(200))
