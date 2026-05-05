from rq import Queue

from app.redis_connection import criar_cliente_redis

redis_conn = criar_cliente_redis()

analysis_queue = Queue("analysis", connection=redis_conn)
