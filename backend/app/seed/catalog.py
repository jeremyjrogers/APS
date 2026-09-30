"""Static reference catalog for synthetic data generation.

Sizing follows what was agreed for the POC: dozens of work centers, dozens of
distinct manufactured/spare parts, a dozen machine-type (project) families,
~50 won projects/year, ~$120M/year aftermarket volume split across sales
orders and overhaul jobs.
"""

WORK_CENTERS = [
    # (id, name, area)
    ("NU-ASM1", "New Unit Assembly Bay 1", "NEW_UNIT"),
    ("NU-ASM2", "New Unit Assembly Bay 2", "NEW_UNIT"),
    ("NU-ASM3", "New Unit Assembly Bay 3", "NEW_UNIT"),
    ("NU-ELEC", "Electrical Panel Build", "NEW_UNIT"),
    ("NU-PIPE", "Skid Piping & Fabrication", "NEW_UNIT"),
    ("NU-PAINT", "New Unit Paint/Coating", "NEW_UNIT"),
    ("NU-TEST1", "Test Stand 1 (Performance)", "NEW_UNIT"),
    ("NU-TEST2", "Test Stand 2 (Performance)", "NEW_UNIT"),
    ("NU-QC", "New Unit Final QC/Inspection", "NEW_UNIT"),
    ("NU-PACK", "New Unit Crating & Prep for Ship", "NEW_UNIT"),
    ("AM-DISASM", "Teardown/Disassembly Bay", "AFTERMARKET"),
    ("AM-CLEAN", "Parts Cleaning", "AFTERMARKET"),
    ("AM-INSP", "Inspection & NDT (Aftermarket)", "AFTERMARKET"),
    ("AM-REASM1", "Repair Reassembly Bay 1", "AFTERMARKET"),
    ("AM-REASM2", "Repair Reassembly Bay 2", "AFTERMARKET"),
    ("AM-BAL", "Dynamic Balancing", "AFTERMARKET"),
    ("AM-TEST", "Aftermarket Test Stand", "AFTERMARKET"),
    ("AM-KIT", "Kitting & Packaging", "AFTERMARKET"),
    ("AM-COAT", "Aftermarket Coating/Plating", "AFTERMARKET"),
    ("AM-QC", "Aftermarket Final QC", "AFTERMARKET"),
    ("SH-CNC1", "CNC Machining Cell 1 (Impellers/Inducers)", "SHARED"),
    ("SH-CNC2", "CNC Machining Cell 2 (Shafts)", "SHARED"),
    ("SH-CNC3", "CNC Machining Cell 3 (Casings/Housings)", "SHARED"),
    ("SH-CNC4", "CNC Turning Cell 4 (Small Precision Parts)", "SHARED"),
    ("SH-WELD", "Welding & Fabrication", "SHARED"),
    ("SH-GRIND", "Precision Grinding", "SHARED"),
    ("SH-NDT", "Shared NDT (Dye Penetrant/UT)", "SHARED"),
    ("SH-HEATTREAT", "Heat Treat", "SHARED"),
    ("SH-KEYWAY", "Keyway/Broaching", "SHARED"),
    ("SH-LAP", "Lapping & Seal Face Finishing", "SHARED"),
    ("SH-TOOLROOM", "Toolroom / Fixture Support", "SHARED"),
]

SUPPLIERS = [
    ("SUP-001", "Ironclad Castings & Foundry", 0.96),
    ("SUP-002", "Meridian Motor Works", 0.98),
    ("SUP-003", "Precision Bearing Supply Co.", 0.95),
    ("SUP-004", "Vanguard Seal Technologies", 0.97),
    ("SUP-005", "Apex Gearbox Systems", 0.93),
    ("SUP-006", "Sterling Steel & Bar Stock", 0.99),
    ("SUP-007", "Continental Electrical Panels", 0.94),
    ("SUP-008", "Summit VFD & Controls", 0.96),
    ("SUP-009", "Redline Forge & Machining", 0.92),
    ("SUP-010", "Coastal Fastener & Gasket Supply", 0.99),
    ("SUP-011", "Titan Casting Group", 0.95),
    ("SUP-012", "Bluewater Coatings", 0.97),
    ("SUP-013", "Highline Lube Systems", 0.94),
    ("SUP-014", "Northgate Instrumentation", 0.96),
    ("SUP-015", "Delta Alloy Supply", 0.98),
]

CUSTOMERS = [
    "Meridian Refining Co.",
    "Coastal Energy Partners",
    "Highline Petrochemical",
    "Bluewater Utilities",
    "Sentinel Power Generation",
    "Palisade Gas Processing",
    "Ironbridge Industrial",
    "Northfield Chemical",
    "Cascade Water Authority",
    "Summit Oil & Gas",
    "Redstone Energy",
    "Lakeshore Paper & Pulp",
    "Vantage Mining Corp",
    "Anchor Terminal Services",
    "Prairie Ethanol Group",
    "Crescent LNG",
    "Delta Marine Services",
    "Foundry Metals Inc.",
    "Overland Pipeline Co.",
    "Continental Food Processing",
]

# item_id, description, item_type, make_or_buy, uom, cost, lead_time_days, supplier_ids
RAW_MATERIALS = [
    ("RM-STEEL-4140", "4140 Alloy Steel Bar Stock", "RM", 45.0, 21, ["SUP-006"]),
    ("RM-STEEL-316", "316 SS Bar Stock", "RM", 68.0, 28, ["SUP-006", "SUP-015"]),
    ("RM-CAST-DI", "Ductile Iron Casting Blank", "RM", 320.0, 42, ["SUP-001", "SUP-011"]),
    ("RM-CAST-CS", "Carbon Steel Casting Blank", "RM", 410.0, 42, ["SUP-001", "SUP-011"]),
    ("RM-CAST-SS", "Stainless Steel Casting Blank", "RM", 890.0, 49, ["SUP-011"]),
    ("RM-GASKET-SHEET", "Gasket Sheet Stock", "RM", 65.0, 10, ["SUP-010"]),
    ("RM-PAINT", "Industrial Coating Material", "RM", 38.0, 7, ["SUP-012"]),
    ("RM-WELDWIRE", "Welding Wire/Consumables", "RM", 22.0, 7, ["SUP-006"]),
]

PURCHASED_COMPONENTS = [
    # id, description, type, cost, lead_time_days, supplier_ids, is_aftermarket
    ("PC-MOTOR-50", "Electric Motor 50HP", "PC", 3200.0, 35, ["SUP-002"], False),
    ("PC-MOTOR-100", "Electric Motor 100HP", "PC", 5800.0, 35, ["SUP-002"], False),
    ("PC-MOTOR-200", "Electric Motor 200HP", "PC", 11500.0, 42, ["SUP-002"], False),
    ("PC-MOTOR-400", "Electric Motor 400HP", "PC", 24000.0, 49, ["SUP-002"], False),
    ("PC-GEARBOX-S", "Gearbox - Small Frame", "PC", 9800.0, 42, ["SUP-005"], False),
    ("PC-GEARBOX-L", "Gearbox - Large Frame", "PC", 26500.0, 56, ["SUP-005"], False),
    ("PC-BEARING-RAD", "Radial Bearing", "PC", 340.0, 14, ["SUP-003"], True),
    ("PC-BEARING-THR", "Thrust Bearing", "PC", 480.0, 14, ["SUP-003"], True),
    ("PC-SEAL-MECH", "Mechanical Seal Cartridge", "PC", 1250.0, 21, ["SUP-004"], True),
    ("PC-SEAL-OSEAL", "O-Ring Seal Set", "PC", 65.0, 7, ["SUP-004"], True),
    ("PC-COUPLING", "Flexible Coupling", "PC", 890.0, 21, ["SUP-005"], True),
    ("PC-VFD", "Variable Frequency Drive", "PC", 6200.0, 28, ["SUP-008"], False),
    ("PC-ELECPANEL", "Electrical Control Panel (base)", "PC", 4800.0, 28, ["SUP-007"], False),
    ("PC-LUBEPUMP", "Lube Oil Pump Unit", "PC", 2100.0, 21, ["SUP-013"], False),
    ("PC-LUBERES", "Lube Oil Reservoir", "PC", 1400.0, 21, ["SUP-013"], False),
    ("PC-SKID-STEEL", "Fabricated Skid Base", "PC", 8600.0, 28, ["SUP-009"], False),
    ("PC-INSTR-PT", "Pressure Transmitter", "PC", 620.0, 14, ["SUP-014"], False),
    ("PC-INSTR-TT", "Temperature Transmitter", "PC", 480.0, 14, ["SUP-014"], False),
    ("PC-INSTR-VIB", "Vibration Sensor", "PC", 750.0, 14, ["SUP-014"], False),
    ("PC-FASTENER-KIT", "Fastener Hardware Kit", "PC", 180.0, 7, ["SUP-010"], False),
    ("PC-GASKET-KIT", "Gasket Kit", "PC", 210.0, 7, ["SUP-010"], True),
    ("PC-FILTER-LUBE", "Lube Oil Filter", "PC", 95.0, 7, ["SUP-013"], True),
    ("PC-COOLER", "Lube Oil Cooler", "PC", 1650.0, 21, ["SUP-013"], False),
    ("PC-GUARD", "Coupling Guard", "PC", 320.0, 14, ["SUP-009"], False),
    ("PC-BASEPLATE", "Machined Baseplate (pre-machined)", "PC", 3400.0, 28, ["SUP-009", "SUP-011"], False),
    ("PC-NAMEPLATE", "Nameplate/Tag Set", "PC", 40.0, 5, ["SUP-010"], False),
]

# item_id, description, family (drives which shared work center), cost,
# lead_time_days, is_aftermarket, machining_hours (per-unit CNC/primary op
# time — differentiated per part, not a flat family rate, since a shim set
# and a large shaft have nothing in common machining-wise despite both being
# in the "shaft" routing family)
MANUFACTURED_PARTS = [
    ("MP-IMPELLER-S", "Impeller - Small (machined)", "impeller", 1450.0, 18, True, 2.5),
    ("MP-IMPELLER-M", "Impeller - Medium (machined)", "impeller", 2600.0, 21, True, 4.0),
    ("MP-IMPELLER-L", "Impeller - Large (machined)", "impeller", 4800.0, 28, True, 6.0),
    ("MP-INDUCER-S", "Inducer - Small (machined)", "impeller", 1100.0, 18, True, 2.0),
    ("MP-INDUCER-M", "Inducer - Medium (machined)", "impeller", 1950.0, 21, True, 3.0),
    ("MP-SHAFT-S", "Shaft - Small (machined)", "shaft", 980.0, 16, True, 2.5),
    ("MP-SHAFT-M", "Shaft - Medium (machined)", "shaft", 1750.0, 18, True, 4.0),
    ("MP-SHAFT-L", "Shaft - Large (machined)", "shaft", 3100.0, 24, True, 6.0),
    ("MP-CASING-S", "Casing/Housing - Small (finish machined)", "casing", 2100.0, 21, True, 3.0),
    ("MP-CASING-M", "Casing/Housing - Medium (finish machined)", "casing", 3800.0, 26, True, 5.0),
    ("MP-CASING-L", "Casing/Housing - Large (finish machined)", "casing", 6600.0, 32, True, 7.0),
    ("MP-WEARRING-S", "Wear Ring - Small", "smallpart", 210.0, 10, True, 0.5),
    ("MP-WEARRING-M", "Wear Ring - Medium", "smallpart", 340.0, 10, True, 0.6),
    ("MP-SLEEVE-SHAFT", "Shaft Sleeve", "smallpart", 260.0, 10, True, 0.5),
    ("MP-BUSHING", "Bushing", "smallpart", 140.0, 8, True, 0.4),
    ("MP-DIFFUSER", "Diffuser (machined)", "impeller", 1600.0, 21, True, 2.0),
    ("MP-ROTORASM", "Rotor Assembly (balanced)", "shaft", 5200.0, 28, False, 3.0),
    ("MP-SEALKIT-STD", "Seal Kit - Standard", "kit", 1450.0, 10, True, 0.0),
    ("MP-SEALKIT-HD", "Seal Kit - Heavy Duty", "kit", 2600.0, 12, True, 0.0),
    ("MP-BEARINGKIT", "Bearing Kit (matched set)", "kit", 950.0, 10, True, 0.0),
    ("MP-OHKIT-S", "Overhaul Kit - Small Frame", "kit", 3200.0, 14, True, 0.0),
    ("MP-OHKIT-M", "Overhaul Kit - Medium Frame", "kit", 5400.0, 14, True, 0.0),
    ("MP-OHKIT-L", "Overhaul Kit - Large Frame", "kit", 8900.0, 18, True, 0.0),
    ("MP-THROATBUSH", "Throat Bushing", "smallpart", 175.0, 8, True, 0.4),
    ("MP-KEYSET", "Keyway/Key Set", "smallpart", 60.0, 5, True, 0.2),
    ("MP-COUPLINGSPACER", "Coupling Spacer (machined)", "smallpart", 410.0, 12, True, 0.6),
    ("MP-BALANCEWEIGHT", "Balance Correction Weight Set", "smallpart", 90.0, 5, True, 0.2),
    ("MP-LABYRINTHSEAL", "Labyrinth Seal Ring", "casing", 380.0, 12, True, 0.8),
    ("MP-IMPELLERHW", "Impeller Retaining Hardware (machined)", "impeller", 120.0, 8, True, 0.2),
    ("MP-SHIMSET", "Precision Shim Set", "smallpart", 45.0, 5, True, 0.15),
]

SUBASSEMBLIES = [
    ("SA-LUBESKID", "Lube Oil Skid Assembly"),
    ("SA-ELECASM", "Electrical Panel & Instrumentation Assembly"),
    ("SA-PIPING", "Skid Interconnect Piping Assembly"),
    ("SA-GUARDASM", "Coupling Guard Assembly"),
]

# machine_type_id, name, family ("PUMP"/"COMPRESSOR"), size ("S"/"M"/"L"), has_lube_skid
MACHINE_TYPES = [
    ("MT-PMP-OH1-S", "Small OH1 Process Pump Package", "PUMP", "S", False),
    ("MT-PMP-OH2-S", "Small OH2 Process Pump Package", "PUMP", "S", False),
    ("MT-PMP-OH2-L", "Large OH2 Process Pump Package", "PUMP", "L", True),
    ("MT-PMP-BB2", "BB2 Between-Bearings Pump Package", "PUMP", "L", True),
    ("MT-PMP-VT", "Vertical Turbine Pump Package", "PUMP", "M", False),
    ("MT-PMP-SEALLESS", "API 682 Sealless Pump Package", "PUMP", "M", False),
    ("MT-PMP-HSC", "Horizontal Split Case Pump Package", "PUMP", "M", True),
    ("MT-PMP-BOOSTER", "Booster Pump Skid Package", "PUMP", "S", False),
    ("MT-CMP-SCREW-S", "Small Screw Compressor Package", "COMPRESSOR", "S", True),
    ("MT-CMP-SCREW-L", "Large Screw Compressor Package", "COMPRESSOR", "L", True),
    ("MT-CMP-CENTRIF", "Centrifugal Compressor Package", "COMPRESSOR", "L", True),
    ("MT-CMP-RECIP", "Reciprocating Compressor Package", "COMPRESSOR", "M", True),
]

SIZE_PROFILE = {
    # size -> (engineering_hrs, assembly_hrs, test_hrs, shared_machining_hrs, lead_time_weeks)
    "S": (120, 180, 40, 90, 10),
    "M": (240, 340, 70, 160, 16),
    "L": (420, 560, 110, 260, 24),
}
