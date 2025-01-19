FROM python:3.9-slim

# ثبّت LibreOffice لتحويل PPTX -> PDF
RUN apt-get update && apt-get install -y libreoffice && apt-get clean

WORKDIR /app

# انسخ ملفات التعريف
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# انسخ بقية الملفات
COPY . .

# شغّل التطبيق (ستستخدم Railway هذا الأمر كنقطة دخول)
CMD ["python", "server.py"]
