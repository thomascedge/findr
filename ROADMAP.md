# Findr Roadmap

Items flagged during scaffolding, ranked by importance.
Check off as completed.

---

## In Progress
- [ ] `messages.py` routes

---

## Up Next

1. **Alembic migrations**
   - Replace `create_tables()` in `db.py` with proper Alembic migration setup
   - Essential before any real data exists that can't be lost

2. **Auth enforcement audit**
   - Verify `get_current_user` is applied consistently across all protected routes
   - Easy to miss during development, critical before any real users

3. **90-day message retention**
   - Celery beat task running nightly
   - Hard delete on `messages` where `deleted_at < NOW() - INTERVAL '90 days'`
   - Soft delete already in place on `Message` model

4. **Celery + Celery beat Docker containers**
   - Prerequisite for retention job and photo moderation
   - Two new containers added to `docker-compose.yml`

5. **Redis + WebSocket presence layer**
   - Real-time map updates
   - Geohash-bucketed pub/sub channels
   - Heartbeat/TTL-based user expiry
   - Core to the app feeling live

6. **Photo upload pipeline**
   - S3 upload → async moderation worker → approved → serve via CDN
   - Requires Celery already running

7. **Search**
   - Interest-based user filtering
   - Postgres array + GIN index now
   - Architected to swap to Elasticsearch later

8. **Elasticsearch logging**
   - Warnings and errors as structured events
   - `event` + `payload` shape
   - Only meaningful once real traffic exists

9. **PostGIS**
   - Swap plain Postgres for PostGIS
   - Replaces Haversine with native spatial queries
   - Worth it at Stage 2 scale (~5K-20K DAUs)

10. **Video chat**
    - WebRTC signaling layer on existing WebSocket setup
    - Coturn container for TURN relay
    - New `WSEventType` entries: `webrtc_offer`, `webrtc_answer`, `webrtc_ice_candidate`

11. **`docker-compose.prod.yml`**
    - Stage 2 architecture
    - Postgres read replica
    - Redis Sentinel
    - Sticky sessions for WebSocket load balancing

12. **LocalStack**
    - Fake AWS locally for S3 and Rekognition
    - Add when building the photo upload pipeline

---

## Notes
- Elasticsearch logging and PostGIS can be introduced together when scaling beyond Austin
- LocalStack blocked on photo pipeline — don't introduce earlier
- Video chat blocked on WebSocket presence layer being stable first
