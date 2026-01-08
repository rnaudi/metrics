# wide events guide

Wide events are a powerful observability pattern where you capture **all context** about a unit of work (like an HTTP request) in a **single event**, rather than scattering it across multiple log lines.

> **AI Usage:** Some examples in this guide were generated with AI assistance to illustrate concepts. The patterns and approaches are based on real observability practices. Always validate with your own context.

## References

- [A Practitioner's Guide to Wide Events](https://jeremymorrell.dev/blog/a-practitioners-guide-to-wide-events/) by Jeremy Morrell
- [Canonical Log Lines](https://brandur.org/canonical-log-lines) by Brandur Leach
- [All you need is Wide Events](https://isburmistrov.substack.com/p/all-you-need-is-wide-events-not-metrics) by Ivan Burmistrov
- [Loggingsucks](https://loggingsucks.com/)

## The Traditional Way (Multiple Log Lines)

```
[2024-01-15 10:23:41] Request started path=/api/login request_id=req_789
[2024-01-15 10:23:41] User lookup user_id=usr_456
[2024-01-15 10:23:42] Auth method detected auth_type=password
[2024-01-15 10:23:42] Rate limit check remaining=95/100
[2024-01-15 10:23:43] Request completed status=200 request_id=req_789
```

**Problem:** Context is scattered. Hard to query. Need to correlate by request_id.

---

## The Wide Event Way (Single Event)

Instead of multiple lines, we emit **ONE event** with **ALL the context**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            WIDE EVENT                                        │
│                         User Login Request                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  START: 2024-01-15 10:23:41.123                                             │
│  END:   2024-01-15 10:23:43.456                                             │
│  DURATION: 2.333s                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  HTTP Context:                                                               │
│    • method: POST                                                            │
│    • route: /api/login                                                       │
│    • status: 200                                                             │
│    • request_id: req_789                                                     │
│                                                                              │
│  User Context:                                                               │
│    • user_id: usr_456                                                        │
│    • user_type: premium                                                      │
│    • user_age_days: 127                                                      │
│    • auth_method: password                                                   │
│                                                                              │
│  Rate Limiting:                                                              │
│    • limit: 100                                                              │
│    • remaining: 95                                                           │
│    • used: 5                                                                 │
│                                                                              │
│  Service Context:                                                            │
│    • service: api-gateway                                                    │
│    • version: v2.4.1                                                         │
│    • instance_id: i-abc123                                                   │
│    • deployment_age_minutes: 45                                              │
│                                                                              │
│  Timings:                                                                    │
│    • auth_duration_ms: 1890                                                  │
│    • db_query_duration_ms: 234                                               │
│    • cache_lookup_duration_ms: 12                                            │
│                                                                              │
│  Feature Flags:                                                              │
│    • feature_flag.new_auth_flow: true                                        │
│    • feature_flag.rate_limit_v2: false                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Example 1: Successful Login

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                          SUCCESSFUL USER LOGIN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

START: 10:23:41.123 ─────────────────────────────────────► END: 10:23:43.456
                                                            
Timeline of operations:                                     Duration: 2.333s
                                                            
├─ [0ms]      Request arrives                              ✓ Success
├─ [12ms]     Cache check for session                      http.status: 200
├─ [234ms]    Database query for user                      error: false
├─ [1890ms]   Password verification (bcrypt)               
├─ [45ms]     Generate JWT token                           
├─ [124ms]    Rate limit check                             
└─ [2333ms]   Response sent                                

CONTEXT CAPTURED:
┌────────────────────────────────────────────────────────────────────────────┐
│ main: true                                                                  │
│ http.method: POST                    user.id: usr_456                      │
│ http.route: /api/login               user.type: premium                    │
│ http.status: 200                     user.auth_method: password            │
│                                      user.age_days: 127                    │
│ service.name: api-gateway                                                  │
│ service.version: v2.4.1              ratelimit.remaining: 95               │
│ service.environment: production      ratelimit.limit: 100                  │
│                                                                             │
│ auth.duration_ms: 1890               cache.session_info: true              │
│ db.query_duration_ms: 234            feature_flag.new_auth_flow: true      │
│                                                                             │
│ user_agent.browser: Chrome           localization.country: USA             │
│ user_agent.device: desktop           localization.currency: USD            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** ALL context is in ONE place. Easy to query:
- "Show me all logins from premium users"
- "Which auth methods are slowest?"
- "What's the p99 for password verification?"

---

## Example 2: Failed Login (Rate Limited)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                        FAILED LOGIN - RATE LIMITED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

START: 14:52:12.891 ───────────────────────────► END: 14:52:12.934
                                                            
Timeline of operations:                          Duration: 43ms
                                                            
├─ [0ms]      Request arrives                   ✗ Failed
├─ [8ms]      Rate limit check                  http.status: 429
├─ [35ms]     Log rate limit violation          error: true
└─ [43ms]     Error response sent               

CONTEXT CAPTURED:
┌────────────────────────────────────────────────────────────────────────────┐
│ main: true                                                                  │
│ http.method: POST                    user.id: usr_789                      │
│ http.route: /api/login               user.type: free                       │
│ http.status: 429                     user.auth_method: password            │
│ http.ip_address: 203.0.113.42       user.age_days: 2                       │
│                                                                             │
│ service.name: api-gateway            ratelimit.remaining: 0                │
│ service.version: v2.4.1              ratelimit.limit: 10                   │
│ service.environment: production      ratelimit.used: 10                    │
│                                      ratelimit.reset_at: 14:53:00          │
│ error: true                                                                 │
│ exception.slug: rate-limit-exceeded  stats.http_requests_count: 1          │
│ exception.message: "Rate limit..."   stats.http_requests_duration_ms: 35   │
│ exception.expected: true                                                    │
│                                                                             │
│ user_agent.browser: Python-requests  # Suspicious: automated bot           │
│ user_agent.device: bot                                                     │
└────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** We can immediately see:
- User is new (age_days: 2)
- User is on free tier (lower rate limits)
- This is a bot (user_agent shows Python-requests)
- Easy to query: "Show me all rate-limited requests from bots"

---

## Why Wide Events Are Powerful

### Traditional Logs
```
❌ Multiple log lines scattered
❌ Need to correlate by ID
❌ Hard to query across dimensions
❌ Missing context
```

### Wide Events
```
✓ ONE event with ALL context
✓ Easy to query: GROUP BY user.type, http.status
✓ Filter on ANY dimension
✓ Visualize patterns instantly
✓ No correlation needed
```

---

## Common Queries Made Easy

With wide events, these queries become trivial:

```sql
-- Which endpoints are slowest for premium users?
SELECT http.route, P99(duration_ms)
WHERE user.type = 'premium'
GROUP BY http.route

-- Show me failed logins from new users
SELECT COUNT(*)
WHERE http.route = '/api/login' 
  AND http.status >= 400
  AND user.age_days < 7
GROUP BY exception.slug

-- Which feature flag correlates with slow requests?
SELECT feature_flag.new_auth_flow, HEATMAP(duration_ms)
WHERE http.route = '/api/login'
GROUP BY feature_flag.new_auth_flow

-- Are recent deployments causing errors?
SELECT service.version, COUNT(*)
WHERE error = true
  AND service.deployment_age_minutes < 30
GROUP BY service.version
```

---

## Key Principles

1. **One Unit of Work = One Event**
   - HTTP request/response = 1 event
   - Background job = 1 event
   - Async task = 1 event

2. **Add ALL Context**
   - User info
   - Service metadata
   - Timings
   - Feature flags
   - Error details
   - Resource usage
   - Literally everything you might want to query

3. **Structure for Machines, Not Humans**
   - Don't worry about "pretty" logs
   - Optimize for queryability
   - Let tools visualize the data

4. **Make it Easy to Slice and Dice**
   - Every attribute = new dimension to explore
   - Use GROUP BY to find patterns
   - Use WHERE to drill down
   - Use HEATMAP to visualize distributions

---
