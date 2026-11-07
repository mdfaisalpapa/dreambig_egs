import frappe

EVENTS = [
    {
        "event_name": "DREAM BIG Flagship Conference Kozhikode",
        "city": "Kozhikode",
        "status": "Open for Registration",
        "event_date": "2026-11-20 09:00:00",
        "registration_deadline": "2026-11-19",
        "venue": "Jamia Hamdard Centre Campus Auditorium, Kozhikode",
        "allow_digital_checkins": 1,
        "allow_digital_food_coupons": 1,
    },
    {
        "event_name": "DREAM BIG Delhi Leadership Summit",
        "city": "Delhi",
        "status": "Open for Registration",
        "event_date": "2026-12-05 09:00:00",
        "registration_deadline": "2026-12-04",
        "venue": "India Islamic Cultural Centre (IICC), Lodhi Road, New Delhi",
        "allow_digital_checkins": 1,
        "allow_digital_food_coupons": 1,
    },
    {
        "event_name": "DREAM BIG Bengaluru Convention",
        "city": "Bengaluru",
        "status": "Open for Registration",
        "event_date": "2026-12-15 09:00:00",
        "registration_deadline": "2026-12-14",
        "venue": "Bengaluru Central Auditorium",
        "allow_digital_checkins": 1,
        "allow_digital_food_coupons": 1,
    },
]

def seed():
    print("Seeding EGS Events...")
    for ev in EVENTS:
        existing = frappe.db.get_value("EGS Event", {"event_name": ev["event_name"]}, "name")
        if not existing:
            doc = frappe.get_doc({
                "doctype": "EGS Event",
                **ev
            })
            doc.insert(ignore_permissions=True)
            print(f"✓ Created Event: {ev['event_name']} ({doc.name})")
        else:
            doc = frappe.get_doc("EGS Event", existing)
            doc.update(ev)
            doc.save(ignore_permissions=True)
            print(f"✓ Updated Event: {ev['event_name']} ({doc.name})")
    frappe.db.commit()
    print("All events seeded successfully!")

if __name__ == "__main__":
    seed()
