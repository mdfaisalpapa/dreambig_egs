import frappe

def setup():
    frappe.set_user("Administrator")
    print("Setting up EGS Portals and PWA...")

    # 1. Enable PWA in Website Settings
    frappe.db.set_value("Website Settings", "Website Settings", "enable_pwa", 1)
    frappe.db.commit()
    print("✓ Enabled PWA in Website Settings")

    # 2. Backfill access_token for existing participants
    participants = frappe.get_all("EGS Student Participant", filters={"access_token": ("is", "not set")}, fields=["name"])
    print(f"Found {len(participants)} participants needing access_token backfill.")
    for p in participants:
        token = frappe.generate_hash(length=15)
        frappe.db.set_value("EGS Student Participant", p.name, "access_token", token)
    frappe.db.commit()
    print("✓ Access tokens backfilled for all existing participants")

    print("\n" + "=" * 50)
    print("Portals and PWA setup successfully completed!")
    print("=" * 50)

if __name__ == "__main__":
    setup()
