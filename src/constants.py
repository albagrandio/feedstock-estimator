# Asset paths

LOGO_TAB_PATH = "assets/verdalia-logo.png"
LOGO_SVG = "assets/trace.svg"
PROCESSED_DATA_PATH = "data/spain_municipality_Ktonnage_EPSG_4326_July24_v2.geojson"

SIGPAC = "fact_sigpac_spain_2024"
CAP = "fact_sigpac_italy"

SHAPEFILE_ITALY = "geofiles_italy_shape"
SHAPEFILE_SPAIN = "georef_spain_municipio"
CONTAINER_NAME = "web-app"
BLOB_NAME_GDF = "spain_municipality_Ktonnage_EPSG_4326_July24_v2.geojson"
BLOB_NAME_BIOWICK = "Biovic_Facilities_24Ap2024.geojson"

crops = [
    "White Wheat (ktn)",
    "Durum Wheat (ktn)",
    "Barley (ktn)",
    "Rye (ktn)",
    "Oatmeal (ktn)",
    "Corn (ktn)",
    "Rice (ktn)",
    "Wheat/Rye (ktn)",
    "Sorgo Grain (ktn)",
    "Cotton (ktn)",
    "Tobacco (ktn)",
]


pigs = [
    "Suma de PORCINOS_Iber (ktn)",
    "Suma de PORCINOS_NonIber (ktn)",
    "POR_madrep_slurry_Iber (ktn)",
    "POR_lech<20kg_slurry_Iber (ktn)",
    "POR_otr_slurry_Iber (ktn)",
    "POR_madrep_slurry_NonIber (ktn)",
    "POR_lech<20kg_slurry_NonIber (ktn)",
    "POR_otr_slurry_NonIber (ktn)",
]

pigs_heads = [
    "POR_madrep_slurry_Iber (no. heads)",
    "POR_lech<20kg_slurry_Iber (no. heads)",
    "POR_otr_slurry_Iber (no. heads)",
    "POR_madrep_slurry_NonIber (no. heads)",
    "POR_lech<20kg_slurry_NonIber (no. heads)",
    "POR_otr_slurry_NonIber (no. heads)",
]

cows = [
    "Total Cow Slurry (kTon)",
    "BO_Ma_>24m (ktn)",
    "BO_No_>24m (ktn)",
    "BO_Ma_<12m (ktn)",
    "BO_Ma_12-24m (ktn)",
    "BO_Va_nomad (ktn)",
    "BO_Va_lech (ktn)",
    "BO_Va_otr (ktn)",
    "BO_BU_otr (ktn)",
]

cows_heads = [
    "Total Cow Slurry (no. heads)",
    "BO_Ma_>24m (no. heads)",
    "BO_No_>24m (no. heads)",
    "BO_Va_lech (no. heads)",
    "Total Cow Manure (no. heads)",
    "BO_Va_otr (no. heads)",
    "BO_Ma_12-24m (no. heads)",
    "BO_Ma_<12m (no. heads)",
    "BO_BU_otr (no. heads)",
    "BO_Va_nomad (no. heads)",
]

sheep = [
    "Total Sheep & Goats Manure (kTon)",
    "OV_madrep (ktn)",
    "OV_otr (ktn)",
    "CAP_madrep (ktn)",
    "CAP_otr (ktn)",
]

sheep_heads = [
    "Total Sheep & Goats (no. heads)",
    "OV_madrep (no. heads)",
    "OV_otr (no. heads)",
    "CAP_madrep (no. heads)",
    "CAP_otr (no. heads)",
]

poultry = [
    "Suma de AVES (ktn)",
    "AVES_poned (ktn)",
    "AVES_broiler (ktn)",
    "AVES_pavos (ktn)",
    "AVES_patos (ktn)",
    "AVES_ocas (ktn)",
    "AVES_avest (ktn)",
    "AVES_otr (ktn)",
]

poultry_heads = [
    "Suma de AVES (no. heads)",
    "AVES_poned (no. heads)",
    "AVES_broiler (no. heads)",
    "AVES_pavos (no. heads)",
    "AVES_patos (no. heads)",
    "AVES_ocas (no. heads)",
    "AVES_avest (no. heads)",
    "AVES_otr (no. heads)",
]

heads_feedstock = [
    "Total Cow Slurry (kTon)",
    "BO_Ma_>24m (ktn)",
    "BO_No_>24m (ktn)",
    "BO_Va_lech (ktn)",
    "Total Cow Manure (kTon)",
    "BO_Va_otr (ktn)",
    "BO_Ma_12-24m (ktn)",
    "BO_Ma_<12m (ktn)",
    "BO_BU_otr (ktn)",
    "BO_Va_nomad (ktn)",
    "Suma de PORCINOS_Iber (ktn)",
    "POR_madrep_slurry_Iber (ktn)",
    "POR_lech<20kg_slurry_Iber (ktn)",
    "POR_otr_slurry_Iber (ktn)",
    "Suma de PORCINOS_NonIber (ktn)",
    "POR_madrep_slurry_NonIber (ktn)",
    "POR_lech<20kg_slurry_NonIber (ktn)",
    "POR_otr_slurry_NonIber (ktn)",
    "CON_TOT (ktn)",
    "HORSE_man (ktn)",
    "Total Sheep & Goats Manure (kTon)",
    "OV_madrep (ktn)",
    "OV_otr (ktn)",
    "CAP_madrep (ktn)",
    "CAP_otr (ktn)",
    "Suma de AVES (ktn)",
    "AVES_poned (ktn)",
    "AVES_broiler (ktn)",
    "AVES_pavos (ktn)",
    "AVES_patos (ktn)",
    "AVES_ocas (ktn)",
    "AVES_avest (ktn)",
    "AVES_otr (ktn)",
]

bolded_totals = [
    "Total Crops (kTon)",
    "Total Cow Slurry (kTon)",
    "Total Cow Manure (kTon)",
    "Suma de PORCINOS_Iber (ktn)",
    "Suma de PORCINOS_NonIber (ktn)",
    "CON_TOT (ktn)",
    "Total Sheep & Goats Manure (kTon)",
    "Suma de AVES (ktn)",
]

totals = [
    "White Wheat (ktn)",
    "Durum Wheat (ktn)",
    "Barley (ktn)",
    "Rye (ktn)",
    "Oatmeal (ktn)",
    "Corn (ktn)",
    "Rice (ktn)",
    "Wheat/Rye (ktn)",
    "Sorgo Grain (ktn)",
    "Cotton (ktn)",
    "Tobacco (ktn)",
    "BO_Ma_>24m (ktn)",
    "BO_No_>24m (ktn)",
    "BO_Va_lech (ktn)",
    "BO_Va_otr (ktn)",
    "BO_Ma_12-24m (ktn)",
    "BO_Ma_<12m (ktn)",
    "BO_BU_otr (ktn)",
    "BO_Va_nomad (ktn)",
    "POR_madrep_slurry_Iber (ktn)",
    "POR_lech<20kg_slurry_Iber (ktn)",
    "POR_otr_slurry_Iber (ktn)",
    "POR_madrep_slurry_NonIber (ktn)",
    "POR_lech<20kg_slurry_NonIber (ktn)",
    "POR_otr_slurry_NonIber (ktn)",
    "HORSE_man (ktn)",
    "OV_madrep (ktn)",
    "OV_otr (ktn)",
    "CAP_madrep (ktn)",
    "CAP_otr (ktn)",
    "AVES_poned (ktn)",
    "AVES_broiler (ktn)",
    "AVES_pavos (ktn)",
    "AVES_patos (ktn)",
    "AVES_ocas (ktn)",
    "AVES_avest (ktn)",
    "AVES_otr (ktn)",
]

heads = [
    "BO_Ma_>24m (no. heads)",
    "BO_No_>24m (no. heads)",
    "BO_Va_lech (no. heads)",
    "BO_Va_otr (no. heads)",
    "BO_Ma_12-24m (no. heads)",
    "BO_Ma_<12m (no. heads)",
    "BO_BU_otr (no. heads)",
    "BO_Va_nomad (no. heads)",
    "POR_madrep_slurry_Iber (no. heads)",
    "POR_lech<20kg_slurry_Iber (no. heads)",
    "POR_otr_slurry_Iber (no. heads)",
    "POR_madrep_slurry_NonIber (no. heads)",
    "POR_lech<20kg_slurry_NonIber (no. heads)",
    "POR_otr_slurry_NonIber (no. heads)",
    "CON_TOT (no. heads)",
    "HORSE_man (no. heads)",
    "OV_madrep (no. heads)",
    "OV_otr (no. heads)",
    "CAP_madrep (no. heads)",
    "CAP_otr (no. heads)",
    "AVES_poned (no. heads)",
    "AVES_broiler (no. heads)",
    "AVES_pavos (no. heads)",
    "AVES_patos (no. heads)",
    "AVES_ocas (no. heads)",
    "AVES_avest (no. heads)",
    "AVES_otr (no. heads)",
]


TONNAGECOWSLURRY = ["BO_Va_lech", "BO_Ma_>24m", "BO_No_>24m"]

TONNAGECOWMANURE = [
    "BO_Va_otr",
    "BO_Ma_12-24m",
    "BO_Ma_<12m",
    "BO_BU_otr",
    "BO_Va_nomad",
]
SHEEPGOATMANURE = ["OV_madrep", "OV_otr", "CAP_madrep", "CAP_otr"]

FINALTONNAGECOLS = {
    "Total Crops (kTon)": "Total Crops",
    "White Wheat (ktn)": "White Wheat ",
    "Durum Wheat (ktn)": "Durum Wheat",
    "Barley (ktn)": "Barley",
    "Rye (ktn)": "Rye",
    "Oatmeal (ktn)": "Oatmeal",
    "Corn (ktn)": "Corn",
    "Rice (ktn)": "Rice",
    "Wheat/Rye (ktn)": "Wheat/Rye",
    "Sorgo Grain (ktn)": "Sorgo Grain",
    "Cotton (ktn)": "Cotton",
    "Tobacco (ktn)": "Tobacco",
    "Total Cow Slurry (kTon)": "Total Cow Slurry",
    "BO_Ma_>24m (ktn)": "Male bovines >24 months",
    "BO_No_>24m (ktn)": "Heifers two years or older without calving",
    "BO_Va_lech (ktn)": "Dairy Cows",
    "Total Cow Manure (kTon)": "Total Cow Manure",
    "BO_Va_otr (ktn)": "Other cows",
    "BO_Ma_12-24m (ktn)": "Bovines between 1-2 years",
    "BO_Ma_<12m (ktn)": "Bovines less than 1 year",
    "BO_BU_otr (ktn)": "Buffaloes",
    "BO_Va_nomad (ktn)": "Heifers 1-2 years without calving",
    "Suma de PORCINOS_Iber (ktn)": "Total Iberican Pigs",
    "POR_madrep_slurry_Iber (ktn)": "Iberican Sow Slurry",
    "POR_lech<20kg_slurry_Iber (ktn)": "Iberican piglets <20kg Slurry",
    "POR_otr_slurry_Iber (ktn)": "Other Iberican pigs Slurry",
    "Suma de PORCINOS_NonIber (ktn)": "Total Non Iberican Pigs",
    "POR_madrep_slurry_NonIber (ktn)": "Non Iberican Sow Slurry",
    "POR_lech<20kg_slurry_NonIber (ktn)": "Non Iberican piglets <20kg Slurry",
    "POR_otr_slurry_NonIber (ktn)": "Other Non Iberican pigs Slurry",
    "Total Cow Slurry (kTon)": "Total Cow Slurry",
    "CON_TOT (ktn)": "Total breeding does",
    "HORSE_man (ktn)": "Horses",
    "Total Sheep & Goats Manure (kTon)": "Total Sheep & Goats Manure",
    "OV_madrep (ktn)": "Ewes and replacement lambs",
    "OV_otr (ktn)": "Other sheep",
    "CAP_madrep (ktn)": "Goats",
    "CAP_otr (ktn)": "Other goats",
    "Suma de AVES (ktn)": "Total Poultry",
    "AVES_poned (ktn)": "Laying hens",
    "AVES_broiler (ktn)": "Broilers",
    "AVES_pavos (ktn)": "Turkeys",
    "AVES_patos (ktn)": "Ducks",
    "AVES_ocas (ktn)": "Geese",
    "AVES_avest (ktn)": "Ostriches",
    "AVES_otr (ktn)": "Other poultry",
}

FINALHEADSCOLS = [
    "Total Cow Slurry (no. heads)",
    "BO_Ma_>24m (no. heads)",
    "BO_No_>24m (no. heads)",
    "BO_Va_lech (no. heads)",
    "Total Cow Manure (no. heads)",
    "BO_Va_otr (no. heads)",
    "BO_Ma_12-24m (no. heads)",
    "BO_Ma_<12m (no. heads)",
    "BO_BU_otr (no. heads)",
    "BO_Va_nomad (no. heads)",
    "Suma de PORCINOS_Iber (no. heads)",
    "POR_madrep_slurry_Iber (no. heads)",
    "POR_lech<20kg_slurry_Iber (no. heads)",
    "POR_otr_slurry_Iber (no. heads)",
    "Suma de PORCINOS_NonIber (no. heads)",
    "POR_madrep_slurry_NonIber (no. heads)",
    "POR_lech<20kg_slurry_NonIber (no. heads)",
    "POR_otr_slurry_NonIber (no. heads)",
    "Total Cow Slurry (no. heads)",
    "CON_TOT (no. heads)",
    "HORSE_man (no. heads)",
    "Total Sheep & Goats (no. heads)",
    "OV_madrep (no. heads)",
    "OV_otr (no. heads)",
    "CAP_madrep (no. heads)",
    "CAP_otr (no. heads)",
    "Suma de AVES (no. heads)",
    "AVES_poned (no. heads)",
    "AVES_broiler (no. heads)",
    "AVES_pavos (no. heads)",
    "AVES_patos (no. heads)",
    "AVES_ocas (no. heads)",
    "AVES_avest (no. heads)",
    "AVES_otr (no. heads)",
]
