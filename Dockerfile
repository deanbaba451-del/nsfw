FROM python:3.9-slim

# Video işleme kütüphaneleri için gerekli sistem paketleri (Güncellendi)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Gereksinimleri yükle
RUN pip install --no-cache-dir pyTelegramBotAPI requests Pillow flask opencv-python-headless numpy

CMD ["python", "main.py"]
