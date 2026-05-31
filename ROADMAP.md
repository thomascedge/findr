# Findr Roadmap

Items flagged during scaffolding, ranked by importance.
Check off as completed.

---

## Completed
- [x] Alembic migrations
- [x] Auth enforcement audit
- [x] 90-day message retention (Celery beat)
- [x] Celery + Celery beat Docker containers
- [x] Redis + WebSocket presence layer
- [x] LocalStack
- [x] Photo upload pipeline

---

## V1 — Austin Launch

### Legal & Safety (must have before real users)

1. **Age verification**
   - Collect `date_of_birth` on registration
   - Block users under 18 at signup
   - Add `date_of_birth` column to `users` table

2. **CSAM reporting pipeline**
   - Explicit content → delete from S3, return 400, no DB record
   - CSAM indicators → preserve in S3, set `moderation_status="reported"`
   - Report to NCMEC within 24-48 hours (legally required)
   - Never delete flagged content even if user deletes account
   - Add `"reported"` to `ModerationStatus` enum
   - Add `reported_at` column to `UserPhoto`

3. **User reporting mechanism** (FOSTA-SESTA)
   - `POST /legal/report` — report a user or content
   - New `UserReport` model: reporter_id, reported_id, reason, created_at
   - Admin review queue (can be manual at Austin scale)

4. **COPPA compliance**
   - Block under-13 at signup — hard block, no exceptions
   - Users 13-17 require parental consent flow (can defer if 18+ only app)
   - Simplest path: make Findr 18+ only, verify age at signup

5. **CCPA compliance (California)**
   - Right to know — privacy policy listing all data collected
   - Right to delete — `DELETE /legal/delete-account` hard deletes all PII
   - Add `data_export_requested_at` to `users` table
   - Hard delete worker task — runs 30 days after deactivation

6. **Account hard delete worker**
   - Celery beat task — runs nightly
   - Hard deletes users where `deactivated_at < NOW() - INTERVAL '30 days'`
   - Removes all PII: username, email, bio, location, photos
   - Preserves anonymized data for abuse investigations

### Core Features

7. **Search**
   - Interest-based user filtering
   - Postgres array + GIN index now
   - Architected to swap to Elasticsearch later

8. **`docker-compose.prod.yml`**
   - Stage 2 architecture
   - Postgres read replica
   - Redis Sentinel
   - Sticky sessions for WebSocket load balancing

---

## V2 — US Scale & Feature Expansion

### Privacy & Encryption

9. **E2EE Messages (Signal Protocol)**
   - End-to-end encrypted messages — server never sees plaintext
   - Client generates public/private key pair on device
   - Key exchange via X25519 Diffie-Hellman on first message
   - New model: `UserKeyBundle`
   - New endpoints: `POST /keys`, `GET /keys/{user_id}`
   - Prerequisite: mobile frontend with key management

### Legal Expansion

10. **GDPR compliance (EU expansion)**
    - Right to be forgotten — hard delete within 30 days of request
    - Data portability — `GET /legal/export-data`
    - Explicit consent for location tracking
    - Add `gdpr_consent_at` to `users` table

### Infrastructure

11. **PostGIS**
    - Swap plain Postgres for PostGIS
    - Replaces Haversine with native spatial queries
    - Worth it at Stage 2 scale (~5K-20K DAUs)

12. **Elasticsearch logging**
    - Warnings and errors as structured events
    - `event` + `payload` shape
    - Only meaningful once real traffic exists

### Features

13. **Video chat**
    - WebRTC signaling layer on existing WebSocket setup
    - Coturn container for TURN relay
    - New `WSEventType` entries: `webrtc_offer`, `webrtc_answer`, `webrtc_ice_candidate`

14. **Celery V2 scheduled tasks**
    - `presence.cleanup_stale_presence` — hourly
    - `analytics.aggregate_daily_stats` — nightly at 3am
    - `moderation.retry_failed_photo_reviews` — every 30 minutes

---

## Design Decisions Log

### Photos
- **Format:** WebP — ~30% smaller than JPEG, universal browser support, scales to global
- **Encryption:** SSE-S3 (server-side) — E2EE incompatible with Rekognition moderation
- **Limit:** 3 per user, user-controlled display order
- **Primary photo:** FK on User (`primary_photo_id`) for fast lookup in hot paths
- **Moderation:** Tag-based, policy-agnostic — API consumers set their own thresholds

### Messages
- **Encryption:** E2EE via Signal Protocol (X25519 DH key exchange) — V2
- **Server role:** Store/deliver public keys and ciphertext only
- **Tradeoffs accepted:** No server-side moderation, no search, key loss = data loss
- **Prerequisite:** Mobile frontend with client-side key management

### Legal
- **Age policy:** 18+ only — simplest COPPA compliance path
- **Data retention:** 90 days for messages, 30 days post-deactivation for accounts
- **CSAM:** Preserve and report — never delete flagged content
- **CCPA:** California minimum — GDPR deferred to V2 EU expansion

---

## V2 Extended — US Scale & Beyond

### Infrastructure & Performance

**Database**
- PgBouncer connection pooling — between app and Postgres
- Partition `messages` by month — fast pruning at scale
- Partition `user_locations` by geohash prefix — regional query isolation
- Separate read replicas per region as DAUs grow nationally

**Caching**
- Redis caching for user profiles — hot path on the map
- Cache invalidation strategy when users update profiles
- Separate Redis clusters: presence / caching / Celery

**Search**
- Elasticsearch for interest-based search — already planned
- pgvector for AI-based matching ("find users similar to me")

---

### Features

**Matching & Discovery**
- AI-powered matching based on interaction patterns
- "Who viewed my profile" — new `ProfileView` model
- Blocking and muting — new `UserBlock` model
- Directional distance filtering (not just radius)

**Messaging**
- E2EE — already planned, requires mobile frontend
- Message reactions
- Media messages — photos/videos in chat, separate S3 path
- Read receipts archival strategy — `MessageRead` grows fast at scale

**Notifications**
- Push notifications via SNS
- Email notifications via SES
- In-app notification center — new `Notification` model

**Profiles**
- Verified profiles — Stripe Identity or Persona
- Structured interests taxonomy
- Profile visibility controls (everyone / connections / nobody)

---

### Monetization

**Premium features**
- See who liked you
- Boost profile visibility on the map
- Unlimited photo uploads (currently capped at 3)
- Read receipts toggle

**API tiers**
- Rate limiting per API key
- Webhook support for moderation events
- Third-party app billing

---

### Safety & Trust

**Trust scoring**
- Score users on reports received, moderation flags, account age
- Surface lower-trust users less prominently on the map

**Rate limiting**
- Message rate limiting — prevent harassment
- Location update rate limiting — prevent spoofing
- Photo upload rate limiting — prevent abuse

**Geofencing**
- Restrict app to specific regions during early rollout
- Block users in jurisdictions where app isn't legally cleared

---

### Observability

- Elasticsearch logging — already planned
- Distributed tracing — Jaeger or Datadog
- Metrics — Prometheus + Grafana (DAU, message volume, map density)
- Alerting — PagerDuty for on-call

---

### Legal & Compliance (V2 additions)

- GDPR — already planned for EU expansion
- SOC 2 Type II — required for enterprise/B2B API customers
- App Store compliance — ongoing as Apple/Google update policies
