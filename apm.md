## APM Trace Enrichment

### Distributed Tracing vs Wide Events
- **Distributed tracing (APM)**: captures request flow across services with spans and profiler data – higher storage costs.
- **Wide events**: modern approach capturing all context in single structured events – no profiler overhead, significant cost savings.
- **Trade-off**: APM gives hop-by-hop visibility; wide events give richer dimensional analysis at lower cost.
- **Note**: consider disabling DD profiler to reduce APM costs while maintaining trace metadata enrichment.

See [events.md](events.md) for wide events patterns.

---

### Overview
- **Cost model**: 1 trace = 1 request – adding custom tags is cheap metadata enrichment vs custom metrics.
- **Custom tags**: platform, api-keys, user-ids – enables rich filtering and grouping without metric cardinality explosion.
- **Use case**: correlate business context (user/tenant) with performance data for incident triage and analysis.

### Tomcat Implementation
- **Thread model**: synchronous, thread-per-request – straightforward span access pattern.
- **Approach**: access global span per thread via `GlobalTracer.get().activeSpan()` without concurrency concerns.
- **Safety**: thread-local semantics guarantee span isolation across concurrent requests.

### Netty Implementation
- **Thread model**: asynchronous, event-loop-based – requires careful span propagation across callbacks.
- **Approach**: explicit span attachment to context; avoid thread-local assumptions due to event loop multiplexing.
- **Caution**: spans must be manually propagated through async boundaries (futures, callbacks, reactive chains).

---

