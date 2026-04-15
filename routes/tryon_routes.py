from flask import Blueprint, render_template, request, jsonify
from utils.tryon_engine import overlay_clothing
import os

tryon = Blueprint("tryon", __name__)

# ================= FOLDERS =================
UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ================= TRY-ON HOME =================
@tryon.route("/tryon")
def tryon_page():
    return render_template("tryon/tryon.html")


# ================= AVATAR TRY-ON =================
@tryon.route("/avatar-tryon")
def avatar_tryon():
    return render_template("tryon/avatar-tryon.html")


# ================= AR TRY-ON =================
@tryon.route("/ar-tryon")
def ar_tryon():
    return render_template("tryon/ar-tryon.html")


# ================= UPLOAD PHOTO =================
@tryon.route("/upload-photo")
def upload_photo():
    return render_template("tryon/upload-photo.html")


# ================= AI TRY-ON PAGE =================
@tryon.route("/tryon-ai")
def tryon_ai():
    cloth = request.args.get("cloth")  # get product image if passed
    return render_template("tryon/ai-tryon.html", cloth=cloth)


# ================= PROCESS TRY-ON =================
@tryon.route("/process-tryon", methods=["POST"])
def process_tryon():

    person = request.files.get("person")
    cloth = request.files.get("cloth")

    if not person or not cloth:
        return jsonify({"error": "Missing files"}), 400

    person_path = os.path.join(UPLOAD_FOLDER, person.filename)
    cloth_path = os.path.join(UPLOAD_FOLDER, cloth.filename)

    output_path = os.path.join(OUTPUT_FOLDER, "result.png")

    person.save(person_path)
    cloth.save(cloth_path)

    success = overlay_clothing(person_path, cloth_path, output_path)

    if not success:
        return jsonify({"error": "Pose not detected"}), 400

    return jsonify({
        "result": "/" + output_path
    })


# ================= BMI CALCULATOR =================
@tryon.route("/tryon/get-avatar", methods=["POST"])
def get_avatar():

    data = request.get_json()

    try:
        height_cm = float(data.get("height", 0))
        weight_kg = float(data.get("weight", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input"}), 400

    if height_cm <= 0 or weight_kg <= 0:
        return jsonify({"error": "Height and weight must be greater than 0"}), 400

    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)

    if bmi < 18.5:
        avatar = "skinny"
        size = "S"
        label = "Slim"
    elif bmi < 25:
        avatar = "normal"
        size = "M"
        label = "Regular"
    else:
        avatar = "fat"   # ✅ FIXED (was 'fatt')
        size = "XL"
        label = "Plus Size"

    return jsonify({
        "avatar": avatar,
        "bmi": round(bmi, 1),
        "size": size,
        "label": label,
        "avatar_img": f"/static/images/avatars/{avatar}.png"
    })


# ================= PRODUCT TRY-ON =================
@tryon.route("/tryon/product/<path:filename>")
def tryon_product(filename):
    # Redirect to AI try-on with cloth pre-selected
    cloth_path = f"/static/images/shirts/{filename}"
    return render_template("tryon/ai-tryon.html", cloth=cloth_path)