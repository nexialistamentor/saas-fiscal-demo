import sys
import redis
from rq import Queue

if sys.platform == "win32":
    from rq_win import WindowsWorker as SelectedWorker
else:
    from rq import Worker as SelectedWorker

redis_conn = redis.Redis(host="localhost", port=6379, db=0)
queue = Queue("analysis", connection=redis_conn)
worker = SelectedWorker([queue], connection=redis_conn)
worker.work()
