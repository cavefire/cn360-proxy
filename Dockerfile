FROM debian:12-slim

ENV PYTHONUNBUFFERED=1

RUN apt update
RUN apt install python3 python3-pip -y
RUN pip3 install mitmproxy --break-system-packages

VOLUME [ "/root/.mitmproxy", "/root/logs" ]

COPY ./start.sh /root/start.sh
COPY ./python /root/python

RUN pip3 install -r /root/python/requirements.txt --break-system-packages

# Environment variables
ENV LOCAL_PROXY_IP=192.168.0.254
ENV ROBOT_PORT=80

# Local settings
ENV LOCAL_CONTROL_HOST=0.0.0.0
ENV LOCAL_CONTROL_PORT=4468

# Cloud settings
ENV BLOCK_UPDATE=true

# Caching
ENV CACHE_STATIC=true
ENV DATA_PATH=/root/data

# Interval settings
ENV MAP_INTV=1
ENV PATH_INTV=1
ENV STATUS_INTV=5

# Logging
ENV LOG_PATH=/root/logs

ENV LOG_LEVEL_CRYPTO=INFO
ENV LOG_LEVEL_ECHO=INFO
ENV LOG_LEVEL_HTTP=INFO
ENV LOG_LEVEL_MITM=INFO
ENV LOG_LEVEL_PACKET=INFO
ENV LOG_LEVEL_ROBOTSOCKETSERVER=INFO
ENV LOG_LEVEL_LOCALCONTROLSOCKETSERVER=INFO
ENV LOG_LEVEL_CLOUDSOCKET=INFO

CMD [ "/bin/bash", "/root/start.sh" ]