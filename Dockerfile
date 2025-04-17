FROM python:3.9-slim

# تحديث النظام وتثبيت FFmpeg و SQLite
RUN apt-get update && apt-get install -y ffmpeg sqlite3 && rm -rf /var/lib/apt/lists/*

# نسخ الملفات إلى الحاوية
COPY . /app
WORKDIR /app

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# تشغيل التطبيق
CMD ["python", "main.py"]
