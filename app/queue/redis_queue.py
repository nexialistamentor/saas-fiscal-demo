import redis
from rq import Queue

redis_conn = redis.Redis(host="localhost", port=6379, db=0)

analysis_queue = Queue("analysis", connection=redis_conn)
