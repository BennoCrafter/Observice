FROM python:3.12-slim

WORKDIR /app

COPY assets/requirements.txt assets/requirements.txt
RUN pip install -r assets/requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
