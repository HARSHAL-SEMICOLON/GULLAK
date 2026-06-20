from rapidfuzz import fuzz

KNOWN_MERCHANTS = {
    # Transport
    "PMPML": ("PMPML Bus", "Transport", 0.99),
    "KRUSHNAI PETROLEUM": ("Krushnai Petrol", "Petrol", 0.99),
    "KEDARI SERVICE STATION": ("Kedari Petrol", "Petrol", 0.99),
    "Highway Petroleum Centre": ("Highway Petrol", "Petrol", 0.99),
    "Siddharth Petroleum": ("Siddharth Petrol", "Petrol", 0.99),
    "COCO WARD ADHOC THREE S SERVICE STATION": ("Coco Service Station", "Petrol", 0.95),
    "GHORADESHWAR PARKING": ("Parking", "Transport", 0.99),
    "CAR PARKING": ("Parking", "Transport", 0.99),

    # Food delivery
    "Swiggy": ("Swiggy", "Food", 0.99),
    "SWIGGY": ("Swiggy", "Food", 0.99),
    "Dominos Pizza": ("Domino's", "Food", 0.99),

    # Subscriptions
    "Netflix Entertainment Services India LLP": ("Netflix", "Subscriptions", 0.99),
    "SPOTIFY INDIA PVT LTD": ("Spotify", "Subscriptions", 0.99),
    "MYJIO": ("Jio Recharge", "Subscriptions", 0.99),
    "Google Play": ("Google Play", "Entertainment", 0.95),
    "COSMOFEED": ("Cosmofeed", "Subscriptions", 0.85),

    # Grocery / supermarket
    "AVENUE SUPERMARTS LTD": ("DMart", "Groceries", 0.99),
    "DMART AVENUE SUPERMARTS LTD": ("DMart", "Groceries", 0.99),
    "Milkbasket": ("Milkbasket", "Groceries", 0.99),

    # Health / pharmacy
    "Shri Ganesh Generic Medicine Store": ("Shri Ganesh Pharmacy", "Health", 0.99),
    "MEDPLUS SOPAN BAUG": ("MedPlus", "Health", 0.99),
    "Medicure Chemist And Druggist": ("Medicure Chemist", "Health", 0.99),
    "HELTH LINE CEMIEST AND DRUGGIST": ("Health Line Chemist", "Health", 0.99),
    "Vighnaharta Pathology Laboratory": ("Pathology Lab", "Health", 0.99),
    "OM MEDICARE": ("Om Medicare", "Health", 0.99),
    "JAY MALHAR MEDICAL": ("Jay Malhar Medical", "Health", 0.99),
    "SHIVBA MEDICO 2": ("Shivba Medical", "Health", 0.99),
    "JAY MAMTA MEDICAL": ("Jay Mamta Medical", "Health", 0.99),
    "KISHOR CHEMIST AND SUPER MART": ("Kishor Chemist", "Health", 0.90),

    # Clothing
    "SNITCH APPARELS PRIVATE LIMITED": ("Snitch", "Clothing", 0.99),
    "HENNES N MAURITZ": ("H&M", "Clothing", 0.99),
    "RIVAN COLLECTION": ("Rivan Collection", "Clothing", 0.90),
    "SHRI BALAJI COLLECTION": ("Balaji Collection", "Clothing", 0.85),

    # Entertainment
    "DISTRICT MOVIE TICKET": ("District App", "Entertainment", 0.99),
    "ORBGEN TECHNOLOGIES PRIVATE LIMITED DISTRICT MOVIE UPI": ("District App", "Entertainment", 0.99),
    "SB GAME GALAXY": ("Game Galaxy", "Entertainment", 0.90),
    "ROOTER SPORTS TECHNOLOGIES PRIVATE LIMITED": ("Rooter", "Entertainment", 0.90),

    # Education
    "MIT UNIVERSITY": ("MIT University", "Education", 0.99),
    "MIT ADT XEROX AND STATIONARY": ("MIT Stationery", "Stationery", 0.95),
    "ITVEDANT": ("ITVedant", "Education", 0.90),
    "EVENTBEEP TECHNOSERVICES PRIVATE LIMITED": ("EventBeep", "Education", 0.75),

    # Tech
    "Amazon Pay on Delivery": ("Amazon", "Tech / Devices", 0.70),
    "EKART": ("Flipkart Delivery", "Tech / Devices", 0.65),
    "AWS India": ("AWS", "Tech / Devices", 0.99),
    "A Tech Computers": ("A Tech Computers", "Tech / Devices", 0.90),

    # Stationery
    "Saraswati Stationery General Stores": ("Saraswati Stationery", "Stationery", 0.99),
    "JK STATIONERY": ("JK Stationery", "Stationery", 0.99),
    "YASH COPIERS": ("Yash Copiers", "Stationery", 0.99),
    "Net Zone Cyber Cafe": ("Net Zone Cyber Cafe", "Stationery", 0.85),
    "SARSWATI STATIONERY AND GENRAL STORES": ("Saraswati Stationery", "Stationery", 0.99),

    # P2P
    "kshitij khade": ("kshitij khade", "P2P Transfer", 0.50),
    "Sarika Injanware": ("Sarika Injanware", "P2P Transfer", 0.50),
    "SUVARNA GOPAL SRINIWAS": ("Suvarna Sriniwas", "P2P Transfer", 0.50),
}

def normalize_merchant(raw_name, threshold=80):
    raw_name_upper = raw_name.upper()
    best_match = None
    best_score = 0
    
    for known, (clean, category, conf) in KNOWN_MERCHANTS.items():
        score = fuzz.token_sort_ratio(raw_name_upper, known.upper())
        if score > best_score:
            best_score = score
            best_match = (clean, category, conf)

    if best_score >= threshold and best_match:
        clean, category, base_conf = best_match
        return clean, category, round(base_conf * (best_score / 100), 2)
    
    return raw_name, "Other", 0.40
