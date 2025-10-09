# Use the official Python 3.13 base image
FROM python:3.13

WORKDIR /app

COPY final_app.py /app/
COPY requirements.txt /app/

# Install OpenCV and MoviePy system dependencies
RUN apt-get update && apt-get install -y libgl1 ffmpeg

RUN pip install --no-cache-dir -r requirements.txt

CMD ["streamlit", "run", "final_app.py"]

