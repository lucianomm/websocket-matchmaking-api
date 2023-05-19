# Using aws ecr public image to avoid pull limit in dockerhub
FROM public.ecr.aws/docker/library/python:3.9

WORKDIR /app

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/server.py ./
COPY app/templates ./templates

EXPOSE 80

CMD ["python", "server.py"]