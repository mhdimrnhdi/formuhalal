import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app, origins=[os.getenv("FRONTEND_URL", "http://localhost:8000")])


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/formulation")
def formulation():
    data = request.get_json(silent=True) or {}
    product_name = (data.get("product_name") or "").strip()
    ingredients = (data.get("ingredients") or "").strip()
    substitute_for = (data.get("substitute_for") or "").strip()

    if not product_name or not ingredients or not substitute_for:
        return jsonify({"error": "product_name, ingredients, and substitute_for are required"}), 400

    return jsonify(
        {
            "product_name": product_name,
            "result": {
                "original": substitute_for,
                "substitute": "Bovine Gelatin (Halal-Certified)",
                "ratio": "1:1",
                "reasoning": (
                    "Bovine gelatin sourced from halal-certified cattle provides identical gelling "
                    "properties with a bloom strength of 200-255. Suitable for confectionery, "
                    "pharmaceutical capsules, and dessert applications. JAKIM certified alternatives "
                    "available from Malaysian suppliers."
                ),
            },
            "suppliers": [
                {
                    "name": "Halal Ingredients Sdn Bhd",
                    "location": "Selangor, Malaysia",
                    "certifications": ["JAKIM", "MUIS", "MUI"],
                    "rating": 4.9,
                    "leadTime": "3-5 days",
                    "minOrder": "100 kg",
                },
                {
                    "name": "Pure Halal Solutions",
                    "location": "Penang, Malaysia",
                    "certifications": ["JAKIM", "IFANCA"],
                    "rating": 4.7,
                    "leadTime": "5-7 days",
                    "minOrder": "50 kg",
                },
                {
                    "name": "MyHalal Trading Co.",
                    "location": "Johor Bahru, Malaysia",
                    "certifications": ["JAKIM", "ESMA"],
                    "rating": 4.8,
                    "leadTime": "2-4 days",
                    "minOrder": "200 kg",
                },
            ],
        }
    )
