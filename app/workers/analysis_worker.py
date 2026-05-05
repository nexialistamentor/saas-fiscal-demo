import sys

from rq import Queue

from app.redis_connection import criar_cliente_redis

if sys.platform == "win32":
    from rq_win import WindowsWorker as SelectedWorker
else:
    from rq import Worker as SelectedWorker

redis_conn = criar_cliente_redis()
queue = Queue("analysis", connection=redis_conn)
worker = SelectedWorker([queue], connection=redis_conn)
worker.work()
