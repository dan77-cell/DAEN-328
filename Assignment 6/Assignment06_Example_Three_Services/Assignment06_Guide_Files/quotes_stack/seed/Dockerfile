FROM python:3.12-slim
WORKDIR /app
# Copy requirements first: Docker caches this layer, so editing seed.py does not reinstall packages.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY seed.py .
CMD ["python", "seed.py"]
