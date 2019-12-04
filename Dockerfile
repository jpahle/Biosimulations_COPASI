FROM ubuntu:latest


RUN apt update && apt install python3 python3-pip python3-dev -y
# RUN apt update && apt add --no-cache python3-dev
WORKDIR /app
COPY copasi_api ./
RUN pip3 install --no-cache-dir -r requirements.txt
ARG filename

ENTRYPOINT [ "python3",  "simulation.py"]