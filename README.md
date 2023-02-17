## Azure App Config

* Startup Command: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker mtp_backend.asgi:application`
* Environment:
    * CLIENT_ID
    * DBPASS
    * DBUSER
    * DBHOST
    * DBNAME
    * REDIS_CONNECTION_STR
* Path Mapping:
    * `/backup`: Mapped to a fileshare