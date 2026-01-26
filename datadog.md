## Dashboard Quick Reference

### Pod
- Resource Utilization dashboard (USE) – tracks per-pod CPU, memory, and restart saturation signals.
- Traffic Performance dashboard (RED) – monitors per-pod request rate and duration for overload detection.
- Stability & Incidents dashboard (USE/RED) – surfaces crash loops, OOMKills, and saturation alerts.

### AWS
- Load Balancer Rate dashboard (RED) – shows ALB/ELB ingress rate to understand external pressure.
- Error Split dashboard (RED/USE) – breaks out target_5xx vs elb_5xx for rapid incident triage.
- Latency & Duration dashboard (RED) – evaluates hop-by-hop latency to validate infrastructure SLAs.

### Application
- Endpoint Top-N dashboard (RED) – ranks endpoints by latency and highlights slow handlers under load.
- Error Timeline dashboard (RED) – charts 4xx/5xx bursts to pinpoint failing routes.
- Throughput dashboard (RED/USE) – correlates request rate with worker saturation and capacity needs.

### DynamoDb
- Capacity dashboard (RED/USE) – compares read/write consumption against provisioned capacity and saturation.
- Latency & Error dashboard (RED) – tracks per-table latency with color-coded 4xx/5xx errors and throttles.
- Table Growth dashboard (USE) – follows item count, table size, and growth ratios for planning.
