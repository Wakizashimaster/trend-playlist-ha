FROM python:3.12-slim
RUN pip install --no-cache-dir "tidalapi>=0.8" "beautifulsoup4>=4.12"
WORKDIR /opt/trend
COPY app/ /opt/trend/
COPY worker.py /worker.py
CMD ["python3", "/worker.py"]
