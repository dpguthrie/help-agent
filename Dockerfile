FROM python:3.12-slim

RUN pip install uv

WORKDIR /app
COPY . .
RUN uv pip install --system --no-cache .

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["python", "scripts/startup.py"]
