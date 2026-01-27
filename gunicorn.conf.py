# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:10000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 4
worker_class = "uvicorn.workers.UvicornWorker"  # Changed
timeout = 120
keepalive = 5
