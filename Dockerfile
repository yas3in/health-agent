# pull official base image
FROM python:3.12.11-alpine

# set work directory
RUN mkdir data_voice
WORKDIR /data_voice

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip3 install --upgrade pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY ./entrypoint.sh /data_voice
RUN sed -i 's/\r$//g' /data_voice/entrypoint.sh
RUN chmod +x /data_voice/entrypoint.sh

# copy project
COPY . /data_voice

# run entrypoint.sh
ENTRYPOINT ["/data_voice/entrypoint.sh"]