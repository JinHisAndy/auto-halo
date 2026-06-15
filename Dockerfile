FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install chromium --with-deps

COPY . .

RUN mkdir -p /app/data

EXPOSE 8808

CMD ["python", "run.py"]