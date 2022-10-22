# nginx dockerfile

FROM nginx:latest
ADD nginx.conf /etc/nginx/nginx.conf
ADD certs/77.153.196.68.crt /etc/nginx/ssl/
ADD certs/77.153.196.68.pem /etc/nginx/ssl/ 
ADD certs/77.153.196.68.key /etc/nginx/ssl/
ADD certs/77.153.196.68.csr /etc/nginx/ssl/ 

RUN chmod -R a+w /var/log/nginx
