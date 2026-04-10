FROM python:3.9-slim
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install pyTelegramBotAPI requests Pillow flask opencv-python-headless numpy
CMD ["python", "main.py"]
