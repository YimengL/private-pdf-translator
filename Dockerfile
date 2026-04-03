FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    fonts-symbola \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download de_core_news_md \
 && python -m spacy download en_core_web_md

COPY pipeline.py .
COPY prompt.md .
COPY prompt_en.md .
COPY main.py .
COPY watcher.py .

ENTRYPOINT ["python3", "main.py"]
