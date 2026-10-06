"""JSON-only RQ delivery worker; analytical work runs in a supervised child."""

from redis import Redis
from rq import Queue, SimpleWorker
from rq.serializers import JSONSerializer

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    if settings.queue_backend != "redis_rq" or not settings.redis_url:
        raise SystemExit("Redis worker is not configured")
    connection = Redis.from_url(settings.redis_url)
    queue = Queue("analytics", connection=connection, serializer=JSONSerializer)
    SimpleWorker([queue], connection=connection, serializer=JSONSerializer).work()


if __name__ == "__main__":
    main()
