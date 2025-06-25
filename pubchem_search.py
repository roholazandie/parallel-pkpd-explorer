import pubchempy as pcp
import requests

def get_compound_by_cas(casrn):
    # First try with PubChemPy
    try:
        compounds = pcp.get_compounds(casrn, 'name')
        if compounds:
            print("✅ Found using PubChemPy")
            return compounds[0].to_dict()
    except Exception as e:
        print(f"PubChemPy failed: {e}")

    # Fallback to PubChem REST API
    print("🔁 Trying PubChem REST API...")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{casrn}/JSON"
    response = requests.get(url)

    if response.status_code == 200:
        try:
            data = response.json()
            cid = data['PC_Compounds'][0]['id']['id']['cid']
            compound = pcp.Compound.from_cid(cid)
            print("✅ Found using REST API")
            return compound.to_dict()
        except Exception as e:
            print(f"Parsing REST response failed: {e}")
    else:
        print(f"REST API failed: {response.status_code}")

    return None

# Example usage
# cas_number = "50-00-0"  # Formaldehyde
cas_number = "14762-75-5"
compound_info = get_compound_by_cas(cas_number)

if compound_info:
    print("Compound Info:", compound_info)
else:
    print("❌ Compound not found")
