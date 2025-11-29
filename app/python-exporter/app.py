from prometheus_client import start_http_server, Counter, Gauge, Histogram
import time, random, threading
import math

REQUESTS = Counter("app_requests_total", "Total app requests")
TEMPERATURE = Gauge("app_temperature_celsius", "Simulated temperature")
LATENCY = Histogram("app_latency_seconds", "Request latency seconds", buckets=[0.05,0.1,0.2,0.5,1,2])

def workloop():
    while True:
        REQUESTS.inc()
        temp = 30 + 50 * random.random()
        TEMPERATURE.set(temp)
        with LATENCY.time():
            time.sleep(abs(random.gauss(0.2, 0.1)))
        time.sleep(0.5)

if __name__ == '__main__':
    start_http_server(8000)
    t = threading.Thread(target=workloop)
    t.daemon = True
    t.start()
    # keep main thread alive
    while True:
        time.sleep(10)
