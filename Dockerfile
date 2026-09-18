# استخدام نسخة رسمية خفيفة من بايثون
FROM python:3.10-slim

# تحديد مجلد العمل داخل الـ Container
WORKDIR /app

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع إلى داخل الـ Container
COPY . .

# تشغيل السيرفر باستخدام uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]