import os
import redis
from rq_win import WindowsWorker
from rq import Queue

redis_conn = redis.Redis(host="localhost", port=6379, db=0)

queue = Queue("analysis", connection=redis_conn)

worker = WindowsWorker([queue], connection=redis_conn)
worker.work()
