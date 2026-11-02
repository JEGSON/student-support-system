"""Local-bind production template. Supply reviewed environment externally."""

bind = "127.0.0.1:5050"
workers = 2
worker_class = "gthread"
threads = 8
timeout = 30
graceful_timeout = 30
keepalive = 5
preload_app = False
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
accesslog = "-"
errorlog = "-"
access_log_format = "method=%(m)s status=%(s)s request_id=%({x-request-id}o)s duration_us=%(D)s"
forwarded_allow_ips = ""  # Trust is enforced by the application's exact-hop middleware.
