# Payment Processing System -- Architecture Design Document

**Version:** 2.1  
**Author:** Platform Engineering Team  
**Last Updated:** 2026-02-28  
**Status:** Approved with conditions (see Section 8)

---

## 1. Executive Summary

This document describes the architecture for PayStream, a next-generation payment processing system that will replace the existing monolithic payment gateway (PayGate v3). PayStream is designed to handle 50,000 transactions per second at peak, support multi-currency settlement, and comply with PCI DSS Level 1 requirements. The system adopts an event-driven architecture built on Apache Kafka, with domain services decomposed around payment lifecycle stages.

The migration from PayGate v3 to PayStream will be executed incrementally over 12 months using a strangler-fig pattern, with both systems running in parallel during the transition.

---

## 2. Context and Problem Statement

PayGate v3 has served the organisation for seven years but now presents critical limitations:

- **Scalability ceiling:** PayGate v3 is a vertically-scaled monolith deployed on a single cluster of bare-metal servers. Current peak throughput is 8,000 TPS against a business requirement of 50,000 TPS by Q4 2027.
- **Currency limitations:** PayGate v3 supports 12 currencies. The business requires 45 currencies including real-time FX conversion.
- **Deployment velocity:** A single release of PayGate v3 requires a 4-hour maintenance window. The target is zero-downtime deployments multiple times per day.
- **Compliance burden:** PCI DSS audit preparation currently takes 6 weeks per cycle because of the monolith's broad blast radius.

### 2.1 Goals

1. Support 50,000 TPS sustained with the ability to burst to 80,000 TPS.
2. Multi-currency transaction processing with real-time FX conversion.
3. PCI DSS Level 1 compliance with a reduced audit scope by isolating cardholder data.
4. Zero-downtime deployments.
5. Sub-second (p99 < 800ms) end-to-end transaction latency for domestic payments.
6. Complete migration from PayGate v3 within 12 months of project start.

### 2.2 Non-Goals

- PayStream will not handle invoicing or billing. Those remain in the existing billing system.
- Cryptocurrency support is out of scope for the initial release.
- Physical point-of-sale integration will be deferred to Phase 2.

---

## 3. Architecture Overview

PayStream follows an event-driven microservices architecture. The primary communication mechanism between services is asynchronous event streaming via Apache Kafka, with synchronous REST/gRPC used only where strict request-response semantics are required (e.g., the merchant-facing API gateway).

### 3.1 High-Level Components

| Component | Responsibility | Communication |
|-----------|---------------|---------------|
| API Gateway | Accept merchant requests, authenticate, rate-limit | Sync (gRPC) |
| Payment Orchestrator | Coordinate the payment lifecycle (authorise, capture, refund) | Kafka events + gRPC to downstream |
| Fraud Engine | Real-time fraud scoring using ML models | Kafka consumer, gRPC response |
| Card Vault | Store and tokenise cardholder data (PCI scope) | Sync (mTLS gRPC), isolated network |
| Settlement Service | Batch settlement with acquiring banks | Kafka consumer, SFTP to banks |
| FX Service | Real-time foreign exchange rate lookup and conversion | Sync (gRPC), caches rates |
| Ledger Service | Double-entry accounting ledger for all money movement | Kafka consumer, PostgreSQL |
| Notification Service | Send webhooks, emails, and SMS to merchants | Kafka consumer |
| Reconciliation Service | Match internal ledger entries against bank statements | Batch (daily), Kafka for exceptions |

### 3.2 Component Diagram

```
[Merchant] --> [API Gateway] --> [Payment Orchestrator]
                                       |
                    +------------------+------------------+
                    |                  |                  |
              [Fraud Engine]    [Card Vault]       [FX Service]
                    |                  |                  |
                    +------------------+------------------+
                                       |
                                    [Kafka]
                                       |
              +------------------------+------------------------+
              |                        |                        |
     [Settlement Service]      [Ledger Service]     [Notification Service]
                                                            |
                                                  [Reconciliation Service]
```

---

## 4. Key Architecture Decisions

### ADR-001: Event-Driven vs. Synchronous Communication

**Decision:** Use Apache Kafka as the primary inter-service communication backbone, with synchronous gRPC reserved for the merchant-facing API path and the Card Vault.

**Alternatives considered:**

1. **Fully synchronous (REST/gRPC everywhere):** Simpler to reason about, excellent tooling, familiar to the team. Rejected because synchronous chains of 5+ services create fragile dependency paths, and a single slow service degrades the entire chain. At 50K TPS the latency budget does not permit serial calls through all services.

2. **Fully asynchronous (event-driven everywhere including merchant API):** Maximum decoupling and resilience. Rejected because merchants expect a synchronous authorisation response within 2 seconds. An event-driven merchant API would require long-polling or WebSockets, complicating merchant integration.

3. **Hybrid (chosen):** The merchant-facing path (API Gateway -> Payment Orchestrator -> Fraud Engine -> Card Vault) uses synchronous gRPC for low-latency authorisation. All downstream processing (settlement, ledger, notifications, reconciliation) is event-driven via Kafka. This balances latency requirements with resilience.

**Trade-offs accepted:**
- Eventual consistency: downstream services (ledger, settlement) are eventually consistent with the authorisation decision. A payment may be authorised but not yet reflected in the ledger for up to 5 seconds.
- Operational complexity: running Kafka adds infrastructure burden. Team must develop expertise in Kafka operations, partitioning strategies, and consumer group management.
- Dual communication paradigms: engineers must understand both sync and async patterns, increasing cognitive load.

### ADR-002: Saga Pattern for Payment Lifecycle

**Decision:** Use an orchestration-based saga (via the Payment Orchestrator) rather than choreography-based sagas.

**Alternatives considered:**

1. **Choreography:** Each service listens for events and emits next events. Simple, no central coordinator. Rejected because the payment lifecycle has complex branching (partial captures, split refunds, chargebacks) that is difficult to reason about without a central view.

2. **Orchestration (chosen):** The Payment Orchestrator holds the state machine for each payment and issues commands to downstream services. If a step fails, the orchestrator issues compensating actions.

**Trade-offs accepted:**
- The Payment Orchestrator is a critical single point of coordination. It must be highly available (deployed as a stateless service with state in PostgreSQL + Kafka).
- Tighter coupling between the orchestrator and downstream services than choreography would have.

### ADR-003: Card Data Isolation

**Decision:** Isolate all cardholder data in the Card Vault service, which runs in a separate PCI-scoped network segment with dedicated infrastructure.

**Rationale:** By confining sensitive card data to a single service, the PCI DSS audit scope is limited to the Card Vault and the API Gateway's TLS termination. All other services handle only tokenised references.

**Trade-offs accepted:**
- The Card Vault becomes a hard dependency for authorisation. If it is unavailable, no new card payments can be processed (stored-token payments using existing tokens can still proceed via a read-replica).
- Additional infrastructure cost for the isolated network segment (~$18,000/month).

### ADR-004: Database Strategy

**Decision:** Each service owns its database (database-per-service pattern). The Ledger Service uses PostgreSQL with serialisable isolation for double-entry integrity. Other services use PostgreSQL with read-committed isolation. Settlement and Reconciliation use TimescaleDB for time-series data.

**Alternatives considered:**

1. **Shared database:** Simpler operationally but creates tight coupling and makes independent deployment impossible.
2. **Event sourcing everywhere:** Provides a complete audit trail but significantly increases complexity, especially for the Ledger Service where traditional double-entry accounting models are well understood.

**Trade-offs accepted:**
- Cross-service queries require either data replication (via Kafka consumers that build local read models) or an API call. No direct joins are possible.
- Operational overhead of managing 8+ database instances.

---

## 5. Data Flow: Payment Authorisation

1. Merchant sends an authorisation request to the API Gateway over mTLS.
2. API Gateway validates the API key, applies rate limiting, and forwards to the Payment Orchestrator via gRPC.
3. Payment Orchestrator creates a payment record (status: PENDING) in its database and sends the transaction to the Fraud Engine via gRPC.
4. Fraud Engine scores the transaction using the ML model and returns a risk score within 150ms (p99).
5. If the risk score exceeds the threshold, the Payment Orchestrator declines the transaction and publishes a `payment.declined` event to Kafka.
6. If the risk score is acceptable, the Payment Orchestrator sends the card token to the Card Vault for authorisation with the acquiring bank.
7. Card Vault communicates with the acquiring bank's ISO 8583 interface and returns the authorisation result.
8. Payment Orchestrator updates the payment record (status: AUTHORISED or DECLINED) and publishes the corresponding event to Kafka.
9. Downstream consumers (Ledger, Notification) process the event asynchronously.

**Latency budget (domestic payment, p99):**

| Step | Budget |
|------|--------|
| API Gateway overhead | 20ms |
| Orchestrator logic | 30ms |
| Fraud Engine | 150ms |
| Card Vault + bank round-trip | 500ms |
| Orchestrator commit + Kafka publish | 50ms |
| **Total** | **750ms** |

---

## 6. Scalability Design

### 6.1 Horizontal Scaling

All services except the Card Vault are stateless and horizontally scalable behind a load balancer. The Card Vault scales reads via replicas but writes are single-primary.

### 6.2 Kafka Partitioning

- Payment events are partitioned by `merchant_id` to preserve per-merchant ordering.
- The `payment.authorised` topic will have 120 partitions initially, scaled to 240 if throughput exceeds 30K TPS per topic.
- Consumer groups are sized to match partition counts.

### 6.3 Auto-scaling Policies

- API Gateway: scale on CPU utilisation (target 60%).
- Payment Orchestrator: scale on in-flight request count (target 500 per pod).
- Fraud Engine: scale on inference latency (p99 > 100ms triggers scale-out).
- Kafka consumers: scale on consumer lag (target < 1000 messages).

### 6.4 Capacity Planning

| Load level | TPS | API Gateway pods | Orchestrator pods | Fraud pods | Kafka brokers |
|------------|-----|------------------|-------------------|------------|---------------|
| Normal | 15,000 | 6 | 8 | 4 | 5 |
| Peak | 50,000 | 18 | 24 | 12 | 9 |
| Burst | 80,000 | 28 | 36 | 18 | 12 |

---

## 7. Security and Compliance

### 7.1 PCI DSS Scope Reduction

Only the Card Vault service and the API Gateway's TLS termination are in PCI scope. All other services handle tokenised card references only.

### 7.2 Encryption

- Data in transit: mTLS between all services. TLS 1.3 for external-facing endpoints.
- Data at rest: AES-256 encryption for all databases. Card Vault uses application-level encryption with HSM-managed keys in addition to disk-level encryption.

### 7.3 Authentication and Authorisation

- Merchant API authentication: API keys with HMAC-SHA256 request signing.
- Inter-service authentication: mTLS with short-lived certificates rotated every 24 hours via an internal CA.
- Admin access: SSO with MFA enforced, role-based access control.

### 7.4 Audit Logging

All payment lifecycle events are persisted immutably in the Ledger Service. Admin actions are logged to a separate audit trail with tamper-evident hashing (hash chain).

---

## 8. Open Risks and Concerns

### Risk 1: Kafka Operational Maturity (Likelihood: Medium, Impact: High)

The team has limited production experience with Kafka. Misconfigured retention policies, partition rebalancing during deploys, and consumer lag monitoring are areas of concern. **Mitigation:** Engage a Kafka specialist consultant for the first 6 months.

### Risk 2: Card Vault Availability (Likelihood: Low, Impact: Critical)

The Card Vault is a single-primary service. A primary failure during peak traffic could block all new card authorisations. **Mitigation:** Implement automatic failover with a warm standby. Accepted RTO: 30 seconds.

### Risk 3: FX Rate Staleness (Likelihood: Medium, Impact: Medium)

The FX Service caches exchange rates with a 60-second TTL. During high-volatility periods, merchants could receive quotes that are stale by up to 60 seconds. **Mitigation:** Reduce TTL to 15 seconds during high-volatility windows (detected via rate-of-change monitoring). Accepted risk: some residual staleness.

### Risk 4: Data Migration Integrity (Likelihood: Medium, Impact: High)

Migrating 7 years of transaction history from PayGate v3 to the new Ledger Service is a large effort. Data format differences and missing fields in older records may cause migration errors. **Mitigation:** Run parallel ledgers for 3 months and reconcile daily.

### Risk 5: Settlement Timing (Likelihood: Low, Impact: Medium)

The asynchronous settlement process introduces a variable delay between authorisation and settlement. In rare cases, settlement could be delayed by up to 24 hours if Kafka consumer lag spikes. **Mitigation:** Alerting on consumer lag > 5000 messages; manual intervention SLA of 2 hours.

---

## 9. Technology Stack

| Layer | Technology |
|-------|-----------|
| API Gateway | Envoy Proxy + custom auth filter (Go) |
| Services | Go (Orchestrator, Card Vault, FX), Python (Fraud Engine ML), Java (Ledger) |
| Event Streaming | Apache Kafka 3.7, Confluent Schema Registry |
| Databases | PostgreSQL 16, TimescaleDB 2.x |
| Infrastructure | Kubernetes (EKS), Terraform, ArgoCD |
| Observability | Datadog (metrics, traces, logs), PagerDuty (alerting) |
| CI/CD | GitHub Actions, ArgoCD for GitOps |
| Secrets Management | HashiCorp Vault |

---

## 10. Migration Strategy

### 10.1 Strangler Fig Approach

1. **Phase 1 (Months 1-3):** Deploy PayStream API Gateway alongside PayGate v3. Route 5% of traffic to PayStream for domestic-only, single-currency transactions.
2. **Phase 2 (Months 4-6):** Migrate all domestic transactions to PayStream. PayGate v3 handles international and multi-currency only.
3. **Phase 3 (Months 7-9):** Enable multi-currency support in PayStream. Migrate international transactions. PayGate v3 enters read-only mode for historical lookups.
4. **Phase 4 (Months 10-12):** Complete data migration. Decommission PayGate v3.

### 10.2 Rollback Plan

At each phase, traffic routing can be reverted to PayGate v3 within 5 minutes via a feature flag in the API Gateway. The rollback preserves data consistency because both systems write to the shared Kafka event log during the parallel period.

---

## 11. Team Structure

The PayStream team follows a domain-aligned topology:

- **Payments Core** (6 engineers): Payment Orchestrator, API Gateway
- **Risk & Fraud** (4 engineers): Fraud Engine, rules management
- **Vault & Compliance** (3 engineers): Card Vault, PCI compliance
- **Money Movement** (5 engineers): Settlement, Ledger, Reconciliation, FX Service
- **Platform** (3 engineers): Kafka, Kubernetes, observability, CI/CD
- **QA & Release** (2 engineers): End-to-end testing, release management

---

## 12. Appendix

### 12.1 Glossary

- **Authorisation:** Verification that a payment method is valid and has sufficient funds.
- **Capture:** The actual transfer of funds following an authorisation.
- **Settlement:** The process of transferring captured funds to the merchant's bank account.
- **Chargeback:** A forced reversal of a payment initiated by the cardholder's bank.
- **Tokenisation:** Replacing sensitive card data with a non-sensitive reference (token).

### 12.2 References

- PCI DSS v4.0 Requirements: https://www.pcisecuritystandards.org
- Kafka Documentation: https://kafka.apache.org/documentation
- Saga Pattern: https://microservices.io/patterns/data/saga.html
