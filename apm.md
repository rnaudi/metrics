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

## Troubleshooting with Enriched Traces

Using custom tags: `platform`, `api_key`, `user_id` + standard APM fields (error.message, http.status, duration, etc.)

### Exception Investigation
**Q**: User reports "invalid email" error – what happened?  
**A**: Search `error.message:"invalid email"` + `user_id` → find full trace with: which platform triggered it, API key used, request timing, full stack trace.

**Q**: Token refresh failing for specific API key?  
**A**: Filter `error.message:"token"` + `api_key` → see all failures for that key: platform distribution, affected users, error rate over time.

**Q**: "NullPointerException" in auth flow – reproduction path?  
**A**: Search `error.message:"NullPointer"` + trace spans → see: which endpoint, request parameters, upstream service calls, timing when NPE occurred.

### Performance Issues
**Q**: Why is OpenID login slow for mobile platforms?  
**A**: Group by `platform:"mobile"` + `http.endpoint:"/auth/openid"` → compare duration with web/desktop, identify mobile-specific latency.

**Q**: Which API keys have slowest authentication?  
**A**: Histogram `duration` grouped by `api_key` → identify problematic integrations, correlate with platforms using those keys.

**Q**: Device login P99 latency spiking – which users affected?  
**A**: Filter `http.endpoint:"/auth/device"` + `duration > p99` → examine: user distribution, platform breakdown, API key patterns, time of day.

### API Key Management
**Q**: New API key integration causing errors – what's failing?  
**A**: Filter `api_key:"key_xyz"` + `http.status >= 400` → see: error types, which endpoints fail, platform distribution, affected users.

**Q**: Rate limiting one API key – legitimate or abuse?  
**A**: Query `api_key` + `http.status:429` → check: request volume, user_id cardinality (many users or one?), platform consistency.

**Q**: API key used from unexpected platform – security issue?  
**A**: Filter `api_key:"web_key"` + `platform:"android"` → detect misconfiguration or credential leak across platform boundaries.

### User-Specific Issues
**Q**: Single user experiencing intermittent auth failures?  
**A**: Search `user_id` + `http.status >= 400` → timeline of failures: which platforms, which API keys, error patterns, success rate.

**Q**: User stuck in OTT polling loop – when did it start?  
**A**: Filter `user_id` + `http.endpoint:"/auth/ott/poll"` → view: poll frequency, duration between polls, when polling started, platform.

**Q**: Password auth works but social login fails for user?  
**A**: Compare `user_id` + `http.endpoint:"/auth/password"` vs `http.endpoint:"/auth/oauth"` → see: success rates, error differences, platform correlation.

### Platform Segmentation
**Q**: Android app auth slower than iOS – backend issue?  
**A**: Compare `platform:"android"` vs `platform:"ios"` + same `http.endpoint` → filter out client-side latency, focus on backend duration.

**Q**: Web platform errors spiking – deployment related?  
**A**: Filter `platform:"web"` + `http.status >= 500` + last 30m → correlate with deployment timestamp, identify affected API keys.

**Q**: iOS device login broken after release – configuration drift?  
**A**: Query `platform:"ios"` + `http.endpoint:"/auth/device"` + today → compare error rate with historical, check API key changes.

### Cross-Dimensional Analysis
**Q**: Which platform + API key combination has worst performance?  
**A**: Group by `platform` + `api_key` → heatmap of duration, identify problematic integration patterns.

**Q**: High error rate on endpoint – is it specific users or broad?  
**A**: Filter `http.endpoint` + `http.status >= 400` → group by `user_id` cardinality: many users = service issue, few users = account problem.

**Q**: OTT flow failing for users from specific API integration?  
**A**: Search `api_key` + `http.endpoint:"/auth/ott"` + errors → trace shows: which users, which platforms, token generation vs validation failure.

---
