import os
import csv
import tensorflow as tf
import numpy as np
import requests
from flask import Flask, request, jsonify
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.efficientnet import preprocess_input  # EfficientNet preprocessing

app = Flask(__name__)

#loads the model
model = load_model("model/refined_food_model_efficientnetb7_lookahead_adamw.keras")
print(model.summary())  #this will be used to confirm model loaded correctly

#loading class names
with open("class_names1.txt", "r", encoding="utf-8") as f:
    class_names = [line.strip() for line in f.readlines()]

#loads local calorie data from CSV
def load_local_calorie_data(csv_path="local_calories.csv"):
    calorie_dict = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            print("CSV Headers:", reader.fieldnames)  # To Read Headers
            for row in reader:
                name = row["food_name"].strip()
                try:
                    calorie_dict[name] = float(row["calories"])
                except ValueError:
                    pass
    except Exception as e:
        print(f"Failed to load local calorie data: {e}")
    return calorie_dict

LOCAL_CALORIE_DATA = load_local_calorie_data()

# USDA API details
USDA_API_KEY = "" # Enter Your USDA API KEY 
USDA_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

def get_nutrition(food_item):
    """Fetch full nutrition data from USDA API."""
    params = {
        "query": food_item,
        "api_key": USDA_API_KEY,
        "pageSize": 1
    }
    response = requests.get(USDA_API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        if "foods" in data and len(data["foods"]) > 0:
            nutrients = data["foods"][0].get("foodNutrients", [])
            result = []
            for n in nutrients:
                name = n.get("nutrientName")
                value = n.get("value")
                unit = n.get("unitName")
                if name and value is not None and unit:
                    result.append({
                        "nutrientName": name,
                        "value": value,
                        "unitName": unit
                    })
            return result
    return []

@app.route('/predict', methods=['POST'])
def predict():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        file_path = "temp.jpg"
        file.save(file_path)

        #this will preprocess image
        img = image.load_img(file_path, target_size=(600, 600))
        img_array = image.img_to_array(img)
        img_array = preprocess_input(img_array)
        img_array = np.expand_dims(img_array, axis=0)
        

        #this will predict
        predictions = model.predict(img_array)
        predicted_class = np.argmax(predictions)
        confidence = float(predictions[0][predicted_class])

        #this will clean predicted class name
        raw_name = class_names[predicted_class] if predicted_class < len(class_names) else "Unknown"
        cleaned_name = raw_name.replace('_', ' ')
        cleaned_name = cleaned_name.split('(')[0].strip()
        food_name = cleaned_name

        #this should display log top 5 simular classifications
        probs = predictions[0]
        top_indices = probs.argsort()[-5:][::-1]
        print("\nTop 5 Predictions:")
        for idx in top_indices:
            print(f"{class_names[idx]}: {probs[idx]:.4f}")
        print(f"\nPredicted class: {raw_name}")
        print(f"Cleaned for USDA: {food_name}")

        #first use local calories if available
        if raw_name in LOCAL_CALORIE_DATA:
            calories = LOCAL_CALORIE_DATA[raw_name]
            nutrition = [{
                "nutrientName": "Energy",
                "value": calories,
                "unitName": "kcal",
                "source": "Local Estimation"
            }]
        else:
            #else check the Fallback to USDA
            nutrition = get_nutrition(food_name)
            calories = next((n["value"] for n in nutrition if "energy" in n["nutrientName"].lower()), "Not available")

        return jsonify({
            "prediction": raw_name,
            "calories": calories,
            "confidence": confidence,
            "nutrition": nutrition
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/search', methods=['GET'])
def search():
    try:
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "No query provided"}), 400

        raw_name = query.strip()
        cleaned_name = raw_name.replace('_', ' ')
        cleaned_name = cleaned_name.split('(')[0].strip()

        #start by checking local dataset
        if raw_name in LOCAL_CALORIE_DATA:
            calories = LOCAL_CALORIE_DATA[raw_name]
            nutrition = [{
                "nutrientName": "Energy",
                "value": calories,
                "unitName": "kcal",
                "source": "Local Estimation"
            }]
        else:
            #if not avalible fallback to USDA
            nutrition = get_nutrition(cleaned_name)
            calories = next((n["value"] for n in nutrition if "energy" in n["nutrientName"].lower()), "Not available")

        return jsonify({
            "prediction": raw_name,
            "calories": calories,
            "nutrition": nutrition
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
