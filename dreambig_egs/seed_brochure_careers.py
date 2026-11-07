import frappe

GROUP_INDEX_MAP = {
    "Government/Public Service-Leadership Roles": 1,
    "Institution building": 1,
    "Govt. Regulatory & Development Leadership": 5,
    "Social Welfare and Development": 5,
    "Financial Leadership": 6,
    "Govt. Scientific & Professional leadership": 7,
    "Manufacturing, Services and Trade": 7,
    "Academic excellence & Leadership": 8,
    "Entrepreneurship & Investment": 8,
    "Inventions and Discovery": 12,
    "Consulting & Think tanks": 12,
    "Professional & Business Leadership": 13,
    "Law, Financial & HR Services": 13,
    "Arts, Journalism & Sports": 17,
    "Technology and Digital Innovation": 17,
    "Religious Scholarship": 20,
    "Political Leadership": 21,
    "UN/ Global Organisations": 22,
}

BROCHURE_DATA = [
    # Employee Category
    ("Employee Category (Individual Leadership)", "Government/Public Service-Leadership Roles", "Honest & effective-IAS/IPS/IFS/Central Civil Services"),
    ("Employee Category (Individual Leadership)", "Government/Public Service-Leadership Roles", "Indian Forest/Economic/Engg./Statistical Service"),
    ("Employee Category (Individual Leadership)", "Government/Public Service-Leadership Roles", "Judges in Supreme Court & High Court/Attorney General of India"),
    ("Employee Category (Individual Leadership)", "Government/Public Service-Leadership Roles", "Chief of Defence Staff/Army Staff/Air Staff/Naval Staff"),
    
    ("Employee Category (Individual Leadership)", "Govt. Regulatory & Development Leadership", "University Grants Commission (UGC)"),
    ("Employee Category (Individual Leadership)", "Govt. Regulatory & Development Leadership", "All India Council for Technical Education (AICTE)"),
    ("Employee Category (Individual Leadership)", "Govt. Regulatory & Development Leadership", "National Medical Commission (NMC)"),
    ("Employee Category (Individual Leadership)", "Govt. Regulatory & Development Leadership", "Indian Council of Medical Research (ICMR)"),
    ("Employee Category (Individual Leadership)", "Govt. Regulatory & Development Leadership", "Indian Council of Agricultural Research (ICAR)"),
    
    ("Employee Category (Individual Leadership)", "Financial Leadership", "Governor, Reserve Bank of India"),
    ("Employee Category (Individual Leadership)", "Financial Leadership", "Chairman/Heads of All India Financial Institutions-NABARD, SIDBI, etc."),
    ("Employee Category (Individual Leadership)", "Financial Leadership", "CMDs of Public Sector/Private Banks"),
    ("Employee Category (Individual Leadership)", "Financial Leadership", "Chief Finance Officers of Top Global Companies"),
    
    ("Employee Category (Individual Leadership)", "Govt. Scientific & Professional leadership", "Director General, CSIR-Council of Scientific and Industrial Research"),
    ("Employee Category (Individual Leadership)", "Govt. Scientific & Professional leadership", "Chairman, ISRO/DRDO"),
    
    ("Employee Category (Individual Leadership)", "Academic excellence & Leadership", "Professors in Top Ranking Global Universities"),
    ("Employee Category (Individual Leadership)", "Academic excellence & Leadership", "Vice-Chancellors of Central, State & Private Universities"),
    
    ("Employee Category (Individual Leadership)", "Inventions and Discovery", "Nobel Laureates"),
    ("Employee Category (Individual Leadership)", "Inventions and Discovery", "World's Top Scientists & Vigyan Ratna Awardees"),
    
    ("Employee Category (Individual Leadership)", "Professional & Business Leadership", "Global CEOs/CTOs/COOs of Top Companies of the World"),
    ("Employee Category (Individual Leadership)", "Professional & Business Leadership", "Honest Top Doctors/Engineers/Architects/Lawyers in leadership roles"),
    
    ("Employee Category (Individual Leadership)", "Arts, Journalism & Sports", "Top Creative Artists / Authors / Futurists"),
    ("Employee Category (Individual Leadership)", "Arts, Journalism & Sports", "Nationally/Internationally Acclaimed Sports persons"),
    
    ("Employee Category (Individual Leadership)", "Religious Scholarship", "Global Islamic scholarship with modern education/science"),
    ("Employee Category (Individual Leadership)", "Political Leadership", "Political Leadership: Honest Politicians"),
    
    ("Employee Category (Individual Leadership)", "UN/ Global Organisations", "Heads of World Bank, IMF, UNICEF, UNESCO, WHO"),

    # Employer Category
    ("Employer Category", "Institution building", "Opening of World-class Schools, Colleges, Universities"),
    ("Employer Category", "Institution building", "Opening of World-Class Hospitals/Healthcare"),
    ("Employer Category", "Institution building", "Opening of World-Class Media outlets"),
    
    ("Employer Category", "Social Welfare and Development", "State/National level Civil Society/NGO for Education, Health, Women's Rights"),
    ("Employer Category", "Social Welfare and Development", "Organisation to channelize Zakat at District and State level"),
    
    ("Employer Category", "Financial Leadership", "Private Equity & Venture Capital Firms"),
    ("Employer Category", "Financial Leadership", "Global Investment Banks/Asset Management"),
    
    ("Employer Category", "Manufacturing, Services and Trade", "Deep-tech Manufacturing/ Big Tech like company"),
    ("Employer Category", "Manufacturing, Services and Trade", "E-commerce portals & Supply Chain Management"),
    
    ("Employer Category", "Entrepreneurship & Investment", "Foundation Model & Generative Biology Startups"),
    ("Employer Category", "Entrepreneurship & Investment", "Unicorn Companies"),
    
    ("Employer Category", "Consulting & Think tanks", "Strategy & Management Consulting Firms"),
    ("Employer Category", "Consulting & Think tanks", "Policy Think Tanks"),
    
    ("Employer Category", "Law, Financial & HR Services", "Top firms of India - Law / Chartered Accountancy"),
    ("Employer Category", "Law, Financial & HR Services", "Legal Clinics / Legal Aid/Human Rights programmes"),
    
    ("Employer Category", "Technology and Digital Innovation", "AI, Data Science, Quantum Tech, Biotech, Bioengineering, Robotics")
]

def seed():
    frappe.set_user("Administrator")
    print("Wiping existing EGS Career Pathway records...")
    frappe.db.delete("EGS Career Pathway")
    frappe.db.commit()

    inserted = 0
    print(f"Total brochure entries to process: {len(BROCHURE_DATA)}")

    for category, group, title in BROCHURE_DATA:
        b_idx = GROUP_INDEX_MAP.get(group, 0)
        doc = frappe.get_doc({
            "doctype": "EGS Career Pathway",
            "career_category": category,
            "career_group": group,
            "career_title": title,
            "brochure_index": b_idx,
            "active": 1,
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        inserted += 1
        print(f"[Inserted {inserted}] (Idx {b_idx}) {title} [{category} -> {group}]")

    frappe.db.commit()

    print("\n" + "=" * 50)
    print(f"Seeding completed successfully!")
    print(f"Total Brochure Pathways Inserted: {inserted}")
    print("=" * 50)

    return {"inserted": inserted}

if __name__ == "__main__":
    seed()
