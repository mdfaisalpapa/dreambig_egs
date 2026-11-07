import frappe

def seed():
    faculties = [
        "Faculty of Engineering & Technology",
        "Faculty of Science",
        "Faculty of Arts & Humanities",
        "Faculty of Commerce & Management",
        "Faculty of Law",
        "Faculty of Medicine & Health Sciences"
    ]
    for f in faculties:
        if not frappe.db.exists("EGS Faculty", f):
            frappe.get_doc({"doctype": "EGS Faculty", "faculty_name": f}).insert(ignore_permissions=True)
            print(f"✓ Created Faculty: {f}")
        else:
            print(f"- Faculty already exists: {f}")

    courses = [
        ("B.Tech Mechanical Engineering", "Faculty of Engineering & Technology"),
        ("B.Tech Computer Science", "Faculty of Engineering & Technology"),
        ("B.Tech Civil Engineering", "Faculty of Engineering & Technology"),
        ("B.Sc Physics", "Faculty of Science"),
        ("B.Sc Mathematics", "Faculty of Science"),
        ("B.A. English", "Faculty of Arts & Humanities"),
        ("B.A. History", "Faculty of Arts & Humanities"),
        ("B.Com (Hons)", "Faculty of Commerce & Management"),
        ("BBA", "Faculty of Commerce & Management"),
        ("BA LLB", "Faculty of Law"),
        ("MBBS", "Faculty of Medicine & Health Sciences")
    ]
    for c, f in courses:
        if not frappe.db.exists("EGS Course", c):
            frappe.get_doc({"doctype": "EGS Course", "course_name": c, "faculty": f}).insert(ignore_permissions=True)
            print(f"✓ Created Course: {c} ({f})")
        else:
            print(f"- Course already exists: {c}")

    frappe.db.commit()
    print("✓ All academic faculties and courses seeded successfully!")

if __name__ == "__main__":
    seed()
