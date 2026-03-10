FROM python:3.9-slim

ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 내부 포트 (docker-compose에서 매핑할 용도)
EXPOSE 10000

# gunicorn 실행 (worker 1개, threads 사용으로 스케줄러 보장)
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "2", "app:app"]
