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

# copy project
COPY . /data_voice