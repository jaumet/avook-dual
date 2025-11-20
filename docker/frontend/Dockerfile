FROM nginx:alpine

COPY docker/frontend/default.conf /etc/nginx/conf.d/default.conf

WORKDIR /usr/share/nginx/html

COPY index.html ./
COPY player.html ./
COPY audios-free.json ./
COPY auth ./auth
COPY js ./js
COPY css ./css
COPY imgs ./imgs
COPY AUDIOS ./AUDIOS
