
# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS

import json
from utility.lookupinjson import get_section
from RDM import (
    Model,
    DistributedLoad,
    PointLoadOnBeam,
    MomentOnBeam,
)
from norme.EC3.elu import compression, shear
import os
#from ressource import sec_list

import hmac
from functools import wraps

app = Flask(__name__)
CORS(app)  # Autorise les appels cross-origin depuis Anvil

from dotenv import load_dotenv

load_dotenv()  # charge le fichier .env

API_SECRET_KEY = os.environ.get("API_SECRET_KEY")

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY", "")
        # Comparaison sécurisée contre les attaques par timing
        if not hmac.compare_digest(api_key, API_SECRET_KEY):
            return jsonify({"error": "Clé API invalide"}), 401

        return f(*args, **kwargs)
    return decorated

@app.route('/')
def hello_world():
    return 'Hello from Flask!'

@app.route("/api/pou_cm", methods=["POST"])
@require_api_key
def check_member():
    """
    Endpoint principal de vérification d'un élément acier.
    """
    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        if data is None:
            return jsonify({"error": "Aucun JSON reçu"}), 400

        # --- Récupération des inputs ---
        section_name = data.get("section")      # "IPE 80"
        material_name = data.get("material")    # "S235"
        length = data.get("length")             # en mm
        ned = data.get("N", 0.0)               # effort normal [N]
        vez = data.get("Vz", 0.0)              # effort tranchant [N]
        my = data.get("My", 0.0)               # moment fléchissant [N.mm]

        return jsonify({
            "status": "ok",
            "inputs": {
                "section": section_name,
                "material": material_name,
                "length": length,
                "N": ned,
                "Vz": vez,
                "My": my,
            },
            "results": 42,
        })
    except Exception as e:
        print("ERREUR :", e)  # ← l'erreur exacte
        return jsonify({"error": str(e)}), 500

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"})

@app.route('/section_steel', methods=["POST"])
@require_api_key
def section_steel():
    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        if data is None:
            return jsonify({"error": "Aucun JSON reçu"}), 400

        sec = data.get("sec")
        # 1. On définit le chemin absolu vers ton dossier de ressources
        # Cela évite les erreurs "File Not Found"
        BASE_DIR = os.path.dirname("/home/alex25071/Str-lib/")
        JSON_PATH = os.path.join(BASE_DIR, "ressource", f"{sec}.json")
        #return JSON_PATH

        # 2. On charge les données UNE SEULE FOIS au démarrage (plus rapide)
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            IPE_DATA = json.load(f)
        # 1. On accède à la liste qui est derrière la clé "sections"
        liste_des_objets = IPE_DATA.get("sections", [])

        # 2. On extrait uniquement le champ "Name" de chaque objet
        # On ignore l'élément qui s'appelle "unit" si tu ne veux que les vrais profilés
        noms_profiles = [
            item["Name"]
            for item in liste_des_objets
            if item.get("Name") != "unit"
        ]

        return jsonify({
            "nombre_de_profiles": len(noms_profiles),
            "liste": noms_profiles
        })
    except Exception as e:
        print("ERREUR :", e)  # ← l'erreur exacte
        return jsonify({"error": str(e)}), 500

@app.route('/section_steel_type', methods=["POST"])
@require_api_key
def section_steel_type():

    try:
        section = (
            "IPE", #need to be after HL
            "HD",
            "HE",
            "HL",

            "chs", #need to be first
            "IPN",
            "Le",
            "Lie",
            "rhs_shs",
            "U",
            "UPE",
            "UPN",
        )
        noms_profiles = section


        return jsonify({
            "nombre_de_profiles": len(noms_profiles),
            "liste": noms_profiles
        })
    except Exception as e:
        print("ERREUR :", e)  # ← l'erreur exacte
        return jsonify({"error": str(e)}), 500

@app.route('/section_steel_val', methods=["POST"])
@require_api_key
def section_steel_val():
    # 1. On définit le chemin absolu vers ton dossier de ressources
    # Cela évite les erreurs "File Not Found"
    BASE_DIR = os.path.dirname("/home/alex25071/Str-lib/")
    JSON_PATH = os.path.join(BASE_DIR, "ressource", "IPE.json")
    #return JSON_PATH

    # 2. On charge les données UNE SEULE FOIS au démarrage (plus rapide)
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        IPE_DATA = json.load(f)
    # 1. On accède à la liste qui est derrière la clé "sections"

    try:
        # 1. Récupération des données JSON
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        if not data:
            return jsonify({"error": "Aucun JSON reçu"}), 400

        # --- Récupération des inputs ---
        section_name = data.get("section")      # "IPE 80"

        # 2. Recherche de la section dans la base de données (ton JSON)
        # On utilise ta fonction de librairie
        section_data = get_section(IPE_DATA, section_name)

        if not section_data:
            return jsonify({"error": f"La section '{section_name}' est introuvable"}), 404

        # 3. Extraction et mapping des valeurs techniques
        # On fait correspondre tes noms (b, h, e...) aux clés du JSON (b, h, tw...)
        results = {
            "b": section_data.get("b"),
            "h": section_data.get("h"),
            "e": section_data.get("tw"),      # tw est l'épaisseur de l'âme (souvent noté e)
            "A": section_data.get("A"),
            "Av": section_data.get("Avz"),    # Aire de cisaillement
            "Iy": section_data.get("Iy"),
            "Iz": section_data.get("Iz"),
            "Wy": section_data.get("Wel,y"),  # Module de flexion élastique y
            "Wz": section_data.get("Wel,z"),  # Module de flexion élastique z
            #"acier_class": section_data.get(material_name) # Retourne la classe (ex: 1) pour l'acier choisi
        }

        # 4. Retour de la réponse
        return jsonify({
            "status": "ok",
            "inputs": {
                "section": section_name,
            },
            "section_properties": results
        })

    except Exception as e:
        print("ERREUR :", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/deflection_calc', methods=["POST"])
@require_api_key
def deflection_calc():
    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)


        length = data.get("length")
        E = data.get("E")
        A = data.get("A")
        Iy = data.get("Iy")
        q =  data.get("load")

        m = Model()
        n1 = m.add_node(0, 0, rx=True, ry=True)
        n2 = m.add_node(length, 0, rx=True, ry=True)

        b1 = m.add_element(n1, n2, E=E, A=A, I=Iy)
        b1.add_load(DistributedLoad(fy=-q))

        m.subdivide_all(100)

        m.solve()

        b = m.all_internal_forces()

        x_offset = 0
        x_combined = []
        N_combined = []
        V_combined = []
        M_combined = []

        for elem_name, forces in b.items():
            x = [v + x_offset for v in forces['x']]
            N = forces['N'] if hasattr(forces['N'], '__len__') else [forces['N']] * len(x)
            V = forces['V'] if hasattr(forces['V'], '__len__') else [forces['V']] * len(x)
            M = forces['M'] if hasattr(forces['M'], '__len__') else [forces['M']] * len(x)

            x_combined.extend(x)
            N_combined.extend(N)
            V_combined.extend(V)
            M_combined.extend(M)

            x_offset = x[-1]  # décalage pour l'élément suivant

        return jsonify({"x": x_combined,
                        "N": N_combined,
                        "V": V_combined,
                        "M": M_combined
                        })

    except Exception as e:
        print("ERREUR :", e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/cm_compression_calc', methods=["POST"])
@require_api_key
def cm_compression_calc():
    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

       # print("DATA REÇUE :", data)

        fy = data.get("fy")
        A = data.get("A")
        gamma_m0 = data.get("gamma_m0")
        q =  data.get("load")

        rslt = compression.Compression(Ned=q,A=A,fy=fy,gamma_m0=gamma_m0)


        return jsonify({"nc_rd": rslt.get_nc_rd(True),
                        "verif": rslt.get_verif(True),
                    })

    except Exception as e:
        print("ERREUR :", e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/cm_shear_calc', methods=["POST"])
@require_api_key
def cm_shear_calc():
    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        fy = data.get("fy")
        Av = data.get("Av")
        gamma_m0 = data.get("gamma_m0")
        q =  data.get("load")
        print("before")

        rslt = shear.Shear(Ved=q,A=Av,fy=fy,gamma_m0=gamma_m0)
        print(rslt.get_verif(with_values=True))

        return jsonify({"vpl_rd": rslt.get_vpl_rd(with_values=True),
                        "verif": rslt.get_verif(with_values=True),
                    })

    except Exception as e:
        print("ERREUR :", e)
        return jsonify({"error": str(e)}), 500
