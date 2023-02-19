## Azure App Config

* Startup Command: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker mtp_backend.asgi:application`
* Environment:
    * ENV
    * CLIENT_ID
    * REDIS_CONNECTION_STR
    * DBPASS
    * DBUSER
    * DBHOST
    * DBNAME
* Path Mapping:
    * `/backup`: Mapped to a fileshare