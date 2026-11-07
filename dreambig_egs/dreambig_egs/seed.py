# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe

INSTITUTIONS = [
    {"name": "India Islamic Cultural Centre", "city": "Delhi"},
    {"name": "Jamia Millia Islamia", "city": "Delhi"},
    {"name": "Madina Education Centre", "city": "Hyderabad"},
    {"name": "Andhra Pradesh State Waqf Board", "city": "Hyderabad"},
    {"name": "Era University", "city": "Lucknow"},
    {"name": "Integral University", "city": "Lucknow"},
    {"name": "Eram Degree College", "city": "Lucknow"},
    {"name": "Anjuman-I-Islam Saif Tyabji Girls High School", "city": "Mumbai"},
    {"name": "Humera Khan College", "city": "Mumbai"},
    {"name": "Rizvi College of Arts, Science & Commerce", "city": "Mumbai"},
    {"name": "Shah Zahoor Musafirkhana", "city": "Vijayawada"},
    {"name": "Aligarh Muslim University", "city": "Aligarh"},
    {"name": "Aliah University", "city": "Kolkata"},
    {"name": "B.S. Abdur Rahman Crescent Institute", "city": "Chennai"},
    {"name": "The New College", "city": "Chennai"},
    {"name": "SIET - Justice Basheer Ahmed Sayeed College", "city": "Chennai"},
    {"name": "Quaid-e-Millath Government College for Women", "city": "Chennai"},
    {"name": "M.S. Group of Institutions", "city": "Chennai"},
    {"name": "Al-Ameen Group of Institutions", "city": "Bengaluru"},
    {"name": "MES College of Engineering Kuttippuram", "city": "Kozhikode"},
    {"name": "JDT Islam Group of Institutions", "city": "Kozhikode"},
    {"name": "KMCT Group of Institutions", "city": "Kozhikode"},
    {"name": "AMU Malappuram Centre", "city": "Kozhikode"},
    {"name": "Jamia Hamdard Centre", "city": "Kozhikode"}
]

COORDINATORS = [
    # Delhi
    {"name": "Justice Allah Raham", "role": "Chief Coordinator", "city": "Delhi", "institution": "India Islamic Cultural Centre", "designation": "Former Judge Allahabad High Court & Former Chairperson UP Public Services Tribunal"},
    {"name": "Janab Mohammed Najeeb Ashraf Choudhary IRS Retd.", "role": "Chief Coordinator", "city": "Delhi", "institution": "India Islamic Cultural Centre", "designation": "Former Chief Commissioner of Income Tax New Delhi & Former Pro-VC and Registrar, Jamia Millia Islamia"},
    {"name": "Lt. Gen. Zameer Uddin Shah Retd.", "role": "Chief Coordinator", "city": "Delhi", "institution": "India Islamic Cultural Centre", "designation": "PVSM, SM, VSM, Former Deputy Chief of Indian Army Staff & Former VC, AMU"},
    {"name": "Janab Intisar A. Siddiqui", "role": "Coordinator", "city": "Delhi", "institution": "India Islamic Cultural Centre", "designation": "Former Fisheries Development Commissioner (i/c), Government of India", "contact_number": "+91-8447583996"},
    {"name": "Prof. Haseena Hashia", "role": "Coordinator", "city": "Delhi", "institution": "Jamia Millia Islamia", "designation": "Retd. Professor, Geography Dept, Jamia Millia Islamia", "contact_number": "9910197133"},
    {"name": "Janab Mohammed Nausherawan", "role": "Coordinator", "city": "Delhi", "institution": "India Islamic Cultural Centre", "designation": "PA to President & Manager HR Admin, IICC", "contact_number": "9811028935"},

    # Hyderabad
    {"name": "Janab Mohammed Shafiquzzaman IAS Retd.", "role": "Chief Coordinator", "city": "Hyderabad", "institution": "Madina Education Centre", "designation": "Former Special Chief Secretary to Govts of AP and Telangana"},
    {"name": "Janab Anwarul Huda IPS Retd.", "role": "Chief Coordinator", "city": "Hyderabad", "institution": "Madina Education Centre", "designation": "Former Director General of Police, Andhra Pradesh"},

    # Lucknow
    {"name": "Justice Saeed-Uz-Zaman Siddiqi", "role": "Chief Coordinator", "city": "Lucknow", "institution": "Era University", "designation": "Former Judge Allahabad High Court"},
    {"name": "Janab Javeed Ahmad IPS Retd.", "role": "Chief Coordinator", "city": "Lucknow", "institution": "Integral University", "designation": "Former Director General of Police, Uttar Pradesh"},

    # Mumbai
    {"name": "Janab Shahzad Hussain IAS Retd.", "role": "Chief Coordinator", "city": "Mumbai", "institution": "Anjuman-I-Islam Saif Tyabji Girls High School", "designation": "Former Additional Chief Secretary to Govt of Maharashtra"},

    # Vijayawada
    {"name": "Janab Md. A. Imtiyaz IAS Retd.", "role": "Chief Coordinator", "city": "Vijayawada", "institution": "Shah Zahoor Musafirkhana", "designation": "Former Secretary to Government of Andhra Pradesh"},

    # Aligarh
    {"name": "Prof. Naima Khatoon", "role": "Chief Patron", "city": "Aligarh", "institution": "Aligarh Muslim University", "designation": "Hon'ble Vice-Chancellor, Aligarh Muslim University"},
    {"name": "Prof. Mohd. Mohsin Khan", "role": "Patron", "city": "Aligarh", "institution": "Aligarh Muslim University", "designation": "Professor, Aligarh Muslim University"},
    {"name": "Prof. Aasim Zafar", "role": "Advisor", "city": "Aligarh", "institution": "Aligarh Muslim University", "designation": "Registrar & Professor, Aligarh Muslim University"},
    {"name": "Prof. Aftab Alam", "role": "Chief Coordinator", "city": "Aligarh", "institution": "Aligarh Muslim University", "designation": "Dean, Faculty of International Studies, AMU"},
    {"name": "Prof. Mohammad Athar Ansari", "role": "Chief Coordinator", "city": "Aligarh", "institution": "Aligarh Muslim University", "designation": "Dean Students Welfare, AMU"},

    # Kolkata
    {"name": "Justice Sahidullah Munshi", "role": "Chief Coordinator", "city": "Kolkata", "institution": "Aliah University", "designation": "Former Judge Calcutta High Court & Chairperson, Auqaf Board, West Bengal"},
    {"name": "Janab Sayeed Ahmed Baba IAS Retd.", "role": "Chief Coordinator", "city": "Kolkata", "institution": "Aliah University", "designation": "Former Additional Chief Secretary to Govt of West Bengal & Officiating Chairman, WBSAT"},
    {"name": "Prof. Rafikul Islam", "role": "Chief Coordinator", "city": "Kolkata", "institution": "Aliah University", "designation": "Vice-Chancellor, Aliah University"},

    # Chennai
    {"name": "Justice G.M. Akbar Ali", "role": "Chief Coordinator", "city": "Chennai", "institution": "B.S. Abdur Rahman Crescent Institute", "designation": "Former Judge, Madras High Court"},
    {"name": "Justice K.N. Basha", "role": "Chief Coordinator", "city": "Chennai", "institution": "The New College", "designation": "Former Judge, Madras High Court"},
    {"name": "Dr. K. Salim Ali IPS Retd.", "role": "Chief Coordinator", "city": "Chennai", "institution": "The New College", "designation": "Former DGP Tripura & Former Special Director CBI"},
    {"name": "Mr. Md. Shakeel Akhter IPS Retd.", "role": "Chief Coordinator", "city": "Chennai", "institution": "B.S. Abdur Rahman Crescent Institute", "designation": "Former DGP Tamil Nadu & Former Chief Information Commissioner Tamil Nadu"},
    {"name": "Mr. Syed Muzammil Abbas IFS Retd.", "role": "Chief Coordinator", "city": "Chennai", "institution": "SIET - Justice Basheer Ahmed Sayeed College", "designation": "Former Principal Chief Conservator of Forests & Former HoFF Tamil Nadu"},
    {"name": "Prof. S. Sathikh", "role": "Chief Coordinator", "city": "Chennai", "institution": "The New College", "designation": "Former Vice-Chancellor, University of Madras"},
    {"name": "Janab Basheer Ahmed IAS Retd.", "role": "Chief Coordinator", "city": "Chennai", "institution": "B.S. Abdur Rahman Crescent Institute", "designation": "Lead Strategy & Operations, DREAM BIG Team"},
    {"name": "Dr. Asiammal IPS Retd.", "role": "Chief Coordinator", "city": "Chennai", "institution": "SIET - Justice Basheer Ahmed Sayeed College", "designation": "Former IPS Officer & Star Speaker Moderator"},
    {"name": "Brig. Dr. Umar Farook VSM Retd.", "role": "Chief Coordinator", "city": "Chennai", "institution": "The New College", "designation": "Ph.D., Exercise 2 Lead, DREAM BIG Team"},
    {"name": "Prof. Mohammed Hussain", "role": "Chief Coordinator", "city": "Chennai", "institution": "The New College", "designation": "Former Dean, University of Madras"},
    {"name": "Prof. Abdul Razak Mohamed", "role": "Chief Coordinator", "city": "Chennai", "institution": "B.S. Abdur Rahman Crescent Institute", "designation": "Former Head, Dept of Planning, Anna University"},
    {"name": "Mr. M. Arif Ahmed", "role": "Coordinator", "city": "Chennai", "institution": "The New College", "designation": "IKLAS & Event Operations Lead"},

    # Bengaluru
    {"name": "Ms. M. Shamim Banu IAS Retd.", "role": "Chief Coordinator", "city": "Bengaluru", "institution": "Al-Ameen Group of Institutions", "designation": "Former Additional Chief Secretary to Govt of Karnataka"},
    {"name": "Janab Javed Akhtar IAS Retd.", "role": "Chief Coordinator", "city": "Bengaluru", "institution": "Al-Ameen Group of Institutions", "designation": "Former ACS Health & Family Welfare Karnataka; Member KERC"},
    {"name": "Janab Najib Shah IRS Retd.", "role": "Chief Coordinator", "city": "Bengaluru", "institution": "Al-Ameen Group of Institutions", "designation": "1979 Batch; Former Chairman Central Board of Excise & Customs"},
    {"name": "Prof. A.H. Rajasab", "role": "Chief Coordinator", "city": "Bengaluru", "institution": "Al-Ameen Group of Institutions", "designation": "Former VC Tumkur University & Chairman KSTA"},
    {"name": "Ms. Banu Mushtaq", "role": "Chief Coordinator", "city": "Bengaluru", "institution": "Al-Ameen Group of Institutions", "designation": "Writer, Activist & Lawyer; International Booker Prize Awardee 2025"},

    # Kozhikode
    {"name": "Justice C.K. Abdul Rahim", "role": "Chief Coordinator", "city": "Kozhikode", "institution": "MES College of Engineering Kuttippuram", "designation": "Former Judge Kerala High Court & Former Chairman KAT"},
    {"name": "Janab Mohammed Hakeem IAS Retd.", "role": "Chief Coordinator", "city": "Kozhikode", "institution": "MES College of Engineering Kuttippuram", "designation": "1969 Batch; Former Union Secretary Ministry of Agriculture GoI"},
    {"name": "Lt. Gen. P.M. Hariz Retd.", "role": "Chief Coordinator", "city": "Kozhikode", "institution": "JDT Islam Group of Institutions", "designation": "PVSM, AVSM, SM, VSM; Former GOC-in-C Southern Command Indian Army"},
    {"name": "Janab K.A. Mohammed Noushad IFS Retd.", "role": "Chief Coordinator", "city": "Kozhikode", "institution": "KMCT Group of Institutions", "designation": "1987 Batch; Former Principal Chief Conservator of Forests Kerala"},
    {"name": "Prof. P.K. Abdul Azis", "role": "Chief Coordinator", "city": "Kozhikode", "institution": "AMU Malappuram Centre", "designation": "Former Vice-Chancellor, AMU & CUSAT"}
]


def run_seed():
    """
    Idempotently seeds EGS Institution and EGS Coordinator records.
    Uses frappe.db.exists before inserting.
    Sets doc.flags.ignore_permissions = True.
    """
    inst_inserted = 0
    inst_skipped = 0
    coord_inserted = 0
    coord_skipped = 0

    print("--- Seeding Institutions ---")
    for inst in INSTITUTIONS:
        name = inst["name"].strip()
        city = inst["city"].strip()

        # Check existence by primary key name or institution_name
        if not frappe.db.exists("EGS Institution", name):
            inst_doc = frappe.get_doc({
                "doctype": "EGS Institution",
                "institution_name": name,
                "city": city,
                "institution_type": (
                    "University" if "University" in name
                    else ("College" if "College" in name else "Other")
                )
            })
            inst_doc.flags.ignore_permissions = True
            inst_doc.insert()
            inst_inserted += 1
            print(f"Inserted Institution: {name} ({city})")
        else:
            inst_skipped += 1
            print(f"Skipped (already exists): {name}")

    frappe.db.commit()

    print("\n--- Seeding Coordinators ---")
    for coord in COORDINATORS:
        name = coord["name"].strip()
        role = coord.get("role", "Coordinator")
        city = coord["city"].strip()
        institution = coord.get("institution")
        designation = coord.get("designation")
        contact_number = coord.get("contact_number")

        # Check existence by coordinator_name / docname
        if not frappe.db.exists("EGS Coordinator", name):
            coord_doc_data = {
                "doctype": "EGS Coordinator",
                "coordinator_name": name,
                "full_name": name,
                "role": role,
                "city": city,
                "institution": institution,
                "designation": designation,
            }
            if contact_number:
                coord_doc_data["contact_number"] = contact_number

            coord_doc = frappe.get_doc(coord_doc_data)
            coord_doc.flags.ignore_permissions = True
            coord_doc.insert()
            coord_inserted += 1
            print(f"Inserted Coordinator: {name} - {role} ({city})")
        else:
            coord_skipped += 1
            print(f"Skipped (already exists): {name}")

    frappe.db.commit()

    total_inst = frappe.db.count("EGS Institution")
    total_coord = frappe.db.count("EGS Coordinator")

    result = {
        "institutions_inserted": inst_inserted,
        "institutions_skipped": inst_skipped,
        "total_institutions_in_db": total_inst,
        "coordinators_inserted": coord_inserted,
        "coordinators_skipped": coord_skipped,
        "total_coordinators_in_db": total_coord,
    }

    print("\n--- Summary ---")
    print(result)
    return result
