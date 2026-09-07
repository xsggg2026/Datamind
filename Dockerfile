FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py analyze_selected.py web_portal.py ./
COPY src ./src
COPY templates ./templates
COPY static ./static

ENV DATAMIND_OUTPUT_DIR=/data/output \
    DATAMIND_UPLOAD_DIR=/data/uploads

EXPOSE 8787
# both run artifacts and upload staging survive container replacement
VOLUME ["/data"]

CMD ["python", "web_portal.py", "--host", "0.0.0.0", "--port", "8787"]
