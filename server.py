import os
import time
import subprocess
from threading import Thread

from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
CONVERTED_FOLDER = "converted"

# إنشاء المجلدات إن لم تكن موجودة
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# سنحتفظ بأوقات انتهاء الملفات (لحذفها بعد مدة)
file_expiry = {}  # مثلاً { "file.pptx": 16734123 (وقت يونكس)، "file.pdf": 16734123 }

# مدة بقاء الملف (15 دقيقة)
EXPIRY_DURATION = 15 * 60  # ثواني


def cleanup_worker():
    """خيط (Thread) يعمل بالخلفية لحذف الملفات منتهية المدة."""
    while True:
        now = time.time()
        expired_files = [
            f for f, expiry_time in file_expiry.items() if now > expiry_time
        ]
        for f in expired_files:
            file_path_uploads = os.path.join(UPLOAD_FOLDER, f)
            file_path_converted = os.path.join(CONVERTED_FOLDER, f)
            # حذف من مجلد الرفع
            if os.path.exists(file_path_uploads):
                os.remove(file_path_uploads)
            # حذف من مجلد الناتج
            if os.path.exists(file_path_converted):
                os.remove(file_path_converted)
            # إزالة من القاموس
            del file_expiry[f]
        # كرر الفحص كل 60 ثانية (يمكن تعديلها)
        time.sleep(60)


@app.before_first_request
def start_cleanup_thread():
    """تشغيل خيط الحذف عند أول طلب فقط."""
    thread = Thread(target=cleanup_worker, daemon=True)
    thread.start()


@app.route("/")
def index():
    return "Hello, this is the PPTX-to-PDF converter service!"


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    استلام ملف PPTX، تحويله إلى PDF، وإرجاع رابط التنزيل.
    """
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400
    
    file = request.files["file"]
    filename = file.filename
    
    # تحقّق من الامتداد (اختياري للأمان)
    if not filename.lower().endswith(".pptx"):
        return jsonify({"success": False, "message": "Only PPTX files are allowed"}), 400
    
    # احفظ الملف في مجلد الرفع
    upload_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(upload_path)
    
    # أضف وقت انتهاء الصلاحية للملف
    expiry_time = time.time() + EXPIRY_DURATION
    file_expiry[filename] = expiry_time
    
    # قم بتحويله إلى PDF باستخدام LibreOffice (يجب تثبيتها)
    # لاحظ أننا نحفظ الـPDF في مجلد converted بنفس اسم الملف لكنه بصيغة pdf
    try:
        subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            upload_path,
            "--outdir", CONVERTED_FOLDER
        ], check=True)
    except Exception as e:
        return jsonify({"success": False, "message": f"Error converting file: {e}"}), 500
    
    # اسم ملف pdf الناتج
    pdf_filename = os.path.splitext(filename)[0] + ".pdf"
    pdf_path = os.path.join(CONVERTED_FOLDER, pdf_filename)
    
    # لو نجح التحويل، أضف ملف PDF أيضًا لقائمة الحذف
    file_expiry[pdf_filename] = expiry_time
    
    # ارجع للمستخدم رابط تحميل الملف (مسار "/download/<pdf_filename>")
    return jsonify({
        "success": True,
        "message": "File converted successfully",
        "download_url": f"/download/{pdf_filename}"
    })


@app.route("/download/<pdf_filename>", methods=["GET"])
def download_file(pdf_filename):
    """
    إرجاع ملف الـPDF للتنزيل.
    """
    pdf_path = os.path.join(CONVERTED_FOLDER, pdf_filename)
    if not os.path.exists(pdf_path):
        return jsonify({"success": False, "message": "File not found"}), 404
    
    return send_file(pdf_path, as_attachment=True)


if __name__ == "__main__":
    # شغّل التطبيق محليًا (Railway سيستخدم الأمر المعرّف في Dockerfile)
    app.run(host="0.0.0.0", port=5000)
