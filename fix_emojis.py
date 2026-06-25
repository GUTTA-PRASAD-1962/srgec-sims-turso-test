"""
fix_emojis.py — Replace ???? placeholders with actual emoji characters
in pages/module_home.py based on context clues.
"""
import re

with open('pages/module_home.py', encoding='utf-8') as f:
    content = f.read()

# Map of placeholder patterns to correct emojis based on context
replacements = [
    # Sidebar buttons
    ('"????  Module Dashboard"', '"🏠  Module Dashboard"'),
    ('"???  Back to Portal"', '"◀  Back to Portal"'),
    # Section icons
    ('sec("????"', 'sec("🔍"'),  # Inventory
    ('sec("????"', 'sec("📊"'),  # Stock - will be done sequentially
    # pnav items - Inventory
    ('"????  Asset Search & Edit"', '"📋  Asset Search & Edit"'),
    ('"????  Case Sheets"', '"📄  Case Sheets"'),
    # Stock
    ('"????  Central Stock"', '"🏛  Central Stock"'),
    ('"????  Department Stock"', '"🏢  Department Stock"'),
    # Procurement
    ('"????  Forward Procurement"', '"📤  Forward Procurement"'),
    ('"???  Pending Approvals"', '"✅  Pending Approvals"'),
    ('"??????  Joint Data Entry"', '"✏️  Joint Data Entry"'),
    ('"????  Procurement Log"', '"📋  Procurement Log"'),
    ('"????  Bulk Upload"', '"📥  Bulk Upload"'),
    # Complaints
    ('"????  Raise Complaint"', '"🆕  Raise Complaint"'),
    ('"????  My Inbox"', '"📥  My Inbox"'),
    ('"????  Complaint Register"', '"📂  Complaint Register"'),
    ('"????  Spare Parts Indent"', '"🔩  Spare Parts Indent"'),
    # Warranty
    ('"??????  Warranty Alerts"', '"⚠️  Warranty Alerts"'),
    ('"????  Expiring Soon"', '"📅  Expiring Soon"'),
    # Maintenance
    ('"????  Maintenance Sheet"', '"🔧  Maintenance Sheet"'),
    ('"????  Asset Movement"', '"🚚  Asset Movement"'),
    ('"????  Lab Maint. Register"', '"🏭  Lab Maint. Register"'),
    # Reports
    ('"????  Reports & Export"', '"📊  Reports & Export"'),
    ('"????  Closure Report"', '"📄  Closure Report"'),
    # Administration
    ('"????  User Management"', '"👥  User Management"'),
    ('"????  Dept & Lab Setup"', '"🏫  Dept & Lab Setup"'),
    ('"????  Suppliers"', '"🏭  Suppliers"'),
    ('"????  Role & Privileges"', '"🔐  Role & Privileges"'),
    ('"????  Audit Log"', '"📜  Audit Log"'),
    # Account
    ('"????  Notifications"', '"🔔  Notifications"'),
    ('"????  Change Password"', '"🔑  Change Password"'),
    # Section headers
    ('sec("????", "Inventory"', 'sec("🔍", "Inventory"'),
    ('sec("????", "Stock Registers"', 'sec("📊", "Stock Registers"'),
    ('sec("????", "Procurement"', 'sec("🛒", "Procurement"'),
    ('sec("????", "Complaints"', 'sec("🔧", "Complaints"'),
    ('sec("????", "Warranty"', 'sec("🔒", "Warranty"'),
    ('sec("????", "Maintenance"', 'sec("🛠", "Maintenance"'),
    ('sec("????", "Reports"', 'sec("📈", "Reports"'),
    ('sec("??????", "Administration"', 'sec("⚙️", "Administration"'),
    ('sec("????", "Account"', 'sec("👤", "Account"'),
    # priv_key strings with ???
    ('"Inventory ??? Asset Search & Edit"', '"Inventory — Asset Search & Edit"'),
    ('"Inventory ??? Case Sheets"', '"Inventory — Case Sheets"'),
    ('"Stock ??? Central Stock"', '"Stock — Central Stock"'),
    ('"Stock ??? Department Stock"', '"Stock — Department Stock"'),
    ('"Procurement ??? Forward"', '"Procurement — Forward"'),
    ('"Procurement ??? Pending Approvals"', '"Procurement — Pending Approvals"'),
    ('"Procurement ??? Joint Data Entry"', '"Procurement — Joint Data Entry"'),
    ('"Procurement ??? Log"', '"Procurement — Log"'),
    ('"Procurement ??? Bulk Upload"', '"Procurement — Bulk Upload"'),
    ('"Complaints ??? Raise Complaint"', '"Complaints — Raise Complaint"'),
    ('"Complaints ??? My Inbox"', '"Complaints — My Inbox"'),
    ('"Complaints ??? Complaint Register"', '"Complaints — Complaint Register"'),
    ('"Complaints ??? Spare Parts Indent"', '"Complaints — Spare Parts Indent"'),
    ('"Warranty ??? Alerts"', '"Warranty — Alerts"'),
    ('"Warranty ??? Expiring Soon"', '"Warranty — Expiring Soon"'),
    ('"Maintenance ??? Sheet"', '"Maintenance — Sheet"'),
    ('"Maintenance ??? Asset Movement"', '"Maintenance — Asset Movement"'),
    ('"Maintenance ??? Lab Register"', '"Maintenance — Lab Register"'),
    ('"Administration ??? User Management"', '"Administration — User Management"'),
    ('"Administration ??? Dept & Lab Setup"', '"Administration — Dept & Lab Setup"'),
    ('"Administration ??? Suppliers"', '"Administration — Suppliers"'),
    ('"Administration ??? Role & Privileges"', '"Administration — Role & Privileges"'),
    ('"Administration ??? Audit Log"', '"Administration — Audit Log"'),
    ('"Account ??? Notifications"', '"Account — Notifications"'),
    ('"Account ??? Change Password"', '"Account — Change Password"'),
    # Comments and docstrings
    ('??? Generic module home page', '— Generic module home page'),
    ('??? default to dashboard', '— default to dashboard'),
    ('??? only shows if user can see it', '— only shows if user can see it'),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        count += 1
        print(f"Replaced: {old[:50]}")

with open('pages/module_home.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal replacements: {count}")
