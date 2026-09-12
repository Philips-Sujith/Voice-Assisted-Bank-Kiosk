"""
Standalone Lightweight Redis Server using fakeredis.TcpFakeServer.
Provides native Redis protocol on port 6379 for pub/sub and session caching on Windows.
"""
import logging
import sys
import fakeredis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [RedisBroker]: %(message)s")
logger = logging.getLogger("RedisBroker")

PORT = 6379
HOST = "127.0.0.1"


def main():
    logger.info("Starting Redis Protocol Broker on %s:%d...", HOST, PORT)
    try:
        server = fakeredis.TcpFakeServer((HOST, PORT))
        logger.info("Redis Protocol Broker running on %s:%d. Ready for connections.", HOST, PORT)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Redis Protocol Broker stopped.")
    except Exception as exc:
        logger.error("Redis Protocol Broker error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
