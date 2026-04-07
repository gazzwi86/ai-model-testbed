# RFP Response: Cloud Migration and Modernisation Program

**Submitted to:** Meridian Financial Services, Inc.  
**Submitted by:** CloudPath Solutions, LLC  
**RFP Reference:** MFS-2026-CM-0042  
**Response Date:** 2026-03-01  
**Validity Period:** 90 days from submission  

---

## Table of Contents

1. Executive Summary
2. Company Overview and Qualifications
3. Understanding of Requirements
4. Proposed Solution Architecture
5. Migration Approach and Methodology
6. Security and Compliance
7. Team Structure and Key Personnel
8. Project Timeline and Milestones
9. Pricing and Commercial Terms
10. Service Level Agreements
11. Risk Management
12. Deliverables and Acceptance Criteria
13. References and Case Studies
14. Appendices

---

## 1. Executive Summary

CloudPath Solutions is pleased to submit this proposal in response to Meridian Financial Services' Request for Proposal (RFP) for the Cloud Migration and Modernisation Program. We understand that Meridian seeks to migrate approximately 140 applications from its on-premises data centres in Dallas and Chicago to Amazon Web Services (AWS) over a 24-month period, while modernising key workloads to take advantage of cloud-native capabilities.

Our proposal offers a comprehensive, phased migration strategy that prioritises business continuity, regulatory compliance, and cost optimisation. CloudPath has successfully executed 47 enterprise cloud migrations over the past six years, including 12 for organisations in the financial services sector. We bring deep expertise in AWS landing zone architecture, application modernisation, and financial services compliance frameworks including SOC 2 Type II, PCI DSS, and GLBA.

We propose a total program investment of $14.2 million over 24 months, which includes migration execution, application modernisation, training, and 12 months of post-migration operational support. This proposal represents our best understanding of Meridian's needs based on the information provided in the RFP and the subsequent clarification responses.

---

## 2. Company Overview and Qualifications

### 2.1 About CloudPath Solutions

CloudPath Solutions is a cloud consulting and managed services firm headquartered in Austin, Texas, with regional offices in New York, Chicago, and London. Founded in 2018, CloudPath has grown to 320 employees specialising in cloud migration, infrastructure modernisation, and managed cloud operations.

### 2.2 Relevant Certifications

- AWS Advanced Tier Services Partner
- AWS Migration Competency Partner
- AWS Financial Services Competency (pending -- expected Q3 2026)
- ISO 27001:2022 certified
- SOC 2 Type II audited annually

### 2.3 Financial Services Experience

CloudPath has completed cloud migration engagements for the following financial services clients:

| Client | Scope | Duration | Applications Migrated |
|--------|-------|----------|-----------------------|
| National Trust Bancorp | Full DC migration to AWS | 18 months | 95 applications |
| Pacific Mutual Insurance | Hybrid cloud (AWS + Azure) | 14 months | 62 applications |
| Sterling Credit Union | AWS migration + modernisation | 10 months | 38 applications |
| Atlantic Wealth Management | AWS migration | 12 months | 71 applications |

*Note: Client names are pseudonymised per NDA requirements. References available upon execution of mutual NDA.*

### 2.4 Partnerships

CloudPath maintains technology partnerships with:
- Amazon Web Services (Advanced Tier)
- HashiCorp (Gold Partner)
- Datadog (Partner)
- Palo Alto Networks (Certified Partner)
- Snowflake (Partner)

---

## 3. Understanding of Requirements

### 3.1 Scope Summary

Based on our review of the RFP and the clarification responses dated February 15, 2026, we understand Meridian's requirements as follows:

1. **Application Portfolio:** Migrate approximately 140 applications from two on-premises data centres (Dallas primary, Chicago DR) to AWS.
2. **Modernisation Targets:** Modernise 25-30 high-value applications from monolithic architectures to containerised microservices.
3. **Data Centre Exit:** Achieve full data centre exit for the Dallas facility by Month 20. The Chicago facility will transition to a cold DR site.
4. **Compliance:** Maintain continuous compliance with SOC 2 Type II, PCI DSS Level 1, GLBA, and state-level financial privacy regulations throughout the migration.
5. **Business Continuity:** Zero unplanned downtime for Tier 1 applications during migration. Maximum 4-hour planned maintenance windows for Tier 1 applications.
6. **Cost Targets:** Achieve a 30% reduction in infrastructure Total Cost of Ownership (TCO) within 18 months of full migration.
7. **Training:** Provide comprehensive training to Meridian's internal IT team (approximately 45 staff) to enable self-sufficient cloud operations post-migration.

### 3.2 Assumptions

We have made the following assumptions in preparing this proposal. Any material deviation from these assumptions may require a scope or pricing adjustment:

1. Meridian will provide CloudPath with VPN access to the on-premises environments within 2 weeks of contract signing.
2. Application owners will be available for discovery workshops during the first 10 weeks.
3. The existing application portfolio inventory provided in Appendix B of the RFP is accurate and complete.
4. Meridian's current AWS account structure will be replaced with a new landing zone designed by CloudPath.
5. Meridian will provision a dedicated project manager and executive sponsor for the duration of the program.
6. Third-party software vendors will provide cloud-compatible licences or migration support as needed.
7. Network bandwidth between on-premises data centres and AWS will be provisioned at 10 Gbps via AWS Direct Connect prior to the start of Phase 2.

---

## 4. Proposed Solution Architecture

### 4.1 AWS Landing Zone

CloudPath will design and deploy a multi-account AWS landing zone using AWS Control Tower with customisations via the Customisations for Control Tower (CfCT) framework. The landing zone will include:

- **Account structure:** Separate AWS accounts for each environment tier (Production, Staging, Development) and for shared services (networking, security, logging).
- **Networking:** Hub-and-spoke VPC architecture using AWS Transit Gateway. Direct Connect from Dallas and Chicago data centres at 10 Gbps per site.
- **Identity:** Integration with Meridian's existing Active Directory via AWS IAM Identity Center (successor to AWS SSO). Federated access with MFA enforcement.
- **Security baseline:** AWS Security Hub, GuardDuty, Config Rules, and CloudTrail enabled across all accounts. Centralised logging to a dedicated security account.
- **Guardrails:** Service Control Policies (SCPs) to enforce compliance boundaries (e.g., restrict deployments to approved regions, prevent disabling of CloudTrail).

### 4.2 Application Migration Patterns

Each application will be assessed using the 7 Rs framework and assigned a migration strategy:

| Strategy | Description | Est. Applications |
|----------|-------------|-------------------|
| Rehost (Lift & Shift) | Move to EC2 with minimal changes | 60-70 |
| Replatform | Migrate with minor optimisations (e.g., RDS instead of self-managed DB) | 30-35 |
| Refactor/Rearchitect | Decompose into containers/serverless | 25-30 |
| Retire | Decommission applications no longer needed | 8-10 |
| Retain | Keep on-premises (regulatory or technical constraint) | 3-5 |

### 4.3 Modernisation Approach

Applications selected for refactoring will be containerised using Docker and orchestrated with Amazon EKS (Kubernetes). CloudPath will work with Meridian's development teams to:

1. Decompose monoliths into bounded-context microservices.
2. Implement CI/CD pipelines using GitHub Actions and ArgoCD.
3. Adopt infrastructure-as-code (Terraform) for all cloud resources.
4. Introduce observability (Datadog) across all modernised workloads.

### 4.4 Database Migration

| Source Database | Target | Migration Tool |
|----------------|--------|---------------|
| Oracle 12c (on-premises) | Amazon RDS for PostgreSQL | AWS SCT + DMS |
| SQL Server 2016 | Amazon RDS for SQL Server | AWS DMS |
| MySQL 5.7 | Amazon Aurora MySQL | AWS DMS |
| MongoDB 4.4 | Amazon DocumentDB | mongodump/mongorestore |
| Custom flat-file stores | Amazon S3 + Athena | Custom ETL scripts |

### 4.5 Disaster Recovery

- **Tier 1 applications (18 apps):** Multi-AZ active-active deployment within us-east-1. Cross-region warm standby in us-west-2. RPO: 1 minute. RTO: 15 minutes.
- **Tier 2 applications (45 apps):** Multi-AZ deployment. Cross-region pilot light. RPO: 1 hour. RTO: 4 hours.
- **Tier 3 applications (remaining):** Single-AZ with daily backups to S3 with cross-region replication. RPO: 24 hours. RTO: 24 hours.

---

## 5. Migration Approach and Methodology

### 5.1 Methodology

CloudPath employs a six-phase migration methodology aligned with the AWS Cloud Adoption Framework:

1. **Assess (Weeks 1-10):** Discovery, portfolio analysis, TCO modelling, migration wave planning.
2. **Mobilise (Weeks 8-14):** Landing zone deployment, network provisioning, team onboarding, runbook creation.
3. **Migrate Wave 1 (Weeks 12-24):** Non-production environments and Tier 3 applications. Validate processes.
4. **Migrate Wave 2 (Weeks 20-40):** Tier 2 production applications. Parallel run and cutover.
5. **Migrate Wave 3 (Weeks 36-60):** Tier 1 production applications and modernisation candidates.
6. **Optimise (Weeks 56-72):** Cost optimisation, performance tuning, training completion, handover.

*Note: Phases overlap intentionally to compress the overall timeline.*

### 5.2 Migration Wave Planning

Applications will be grouped into migration waves of 10-15 applications based on:
- Dependency mapping (co-dependent applications migrate together)
- Business criticality (lower tiers first to build confidence)
- Technical complexity
- Application owner availability

### 5.3 Cutover Process

Each application cutover will follow this process:
1. Pre-cutover validation in staging environment.
2. Scheduled maintenance window (communicated 2 weeks in advance).
3. Data sync (final delta replication via DMS).
4. DNS cutover to AWS endpoints.
5. Smoke testing (automated + manual).
6. Hypercare period (72 hours with dedicated support).
7. Sign-off by application owner.

### 5.4 Rollback Plan

Every cutover will have a documented rollback plan. If critical issues are discovered during the hypercare period, traffic will be rerouted to the on-premises environment within 30 minutes. Data written to the cloud during the failed cutover will be replayed to on-premises systems.

---

## 6. Security and Compliance

### 6.1 Compliance Frameworks

CloudPath will ensure continuous compliance with the following frameworks throughout the migration:

- **SOC 2 Type II:** Controls for security, availability, processing integrity, confidentiality, and privacy.
- **PCI DSS Level 1:** For applications that process, store, or transmit cardholder data.
- **GLBA (Gramm-Leach-Bliley Act):** Safeguards for customer financial information.
- **State regulations:** Compliance with the New York DFS Cybersecurity Regulation (23 NYCRR 500) and California Consumer Privacy Act (CCPA).

### 6.2 Compliance During Migration

During the parallel-run period, both on-premises and cloud environments will be in compliance scope. CloudPath will:

1. Extend existing compliance controls to AWS using AWS Config Rules and custom compliance-as-code policies.
2. Perform a mid-migration compliance gap assessment at the end of Phase 3 (Week 24).
3. Support Meridian's annual SOC 2 Type II audit with AWS-specific evidence and artefacts.

*Note: CloudPath's proposal does not include the cost of Meridian's external compliance auditor. Meridian is responsible for engaging its auditor and covering audit fees.*

### 6.3 Data Protection

- **Encryption at rest:** All data at rest will be encrypted using AWS KMS with customer-managed keys (CMKs). Key rotation every 365 days.
- **Encryption in transit:** TLS 1.2 minimum for all internal and external communications. TLS 1.3 for public-facing endpoints.
- **Data residency:** All data will reside in AWS us-east-1 (primary) and us-west-2 (DR). No data will leave the continental United States.
- **Data classification:** CloudPath will work with Meridian to classify data into Confidential, Internal, and Public tiers, applying appropriate controls to each.

### 6.4 Security Operations

- **SIEM integration:** CloudPath will integrate AWS CloudTrail, VPC Flow Logs, and GuardDuty findings into Meridian's existing Splunk SIEM.
- **Vulnerability management:** Weekly vulnerability scans using AWS Inspector and Qualys (Meridian's existing tool).
- **Penetration testing:** CloudPath will conduct one penetration test at the conclusion of Phase 3 and one at the conclusion of Phase 5. Additional penetration tests are available at $45,000 per engagement.

### 6.5 Incident Response

CloudPath will develop an AWS-specific incident response playbook that integrates with Meridian's existing incident response plan. The playbook will cover:
- Compromised IAM credentials
- Data exfiltration attempts
- Ransomware/malware events
- DDoS attacks (leveraging AWS Shield Advanced)

*Note: This proposal does not include the cost of AWS Shield Advanced ($3,000/month + data transfer fees). If Meridian elects to use Shield Advanced, this will be billed separately as an AWS consumption cost.*

---

## 7. Team Structure and Key Personnel

### 7.1 Proposed Team

| Role | Name | Allocation | Experience |
|------|------|------------|------------|
| Program Director | Maria Santos | 100% | 15 years, 9 cloud migrations |
| Solution Architect (Lead) | Chen Wei | 100% | 12 years, AWS SA Professional cert |
| Solution Architect | Priya Sharma | 100% | 8 years, 5 financial services migrations |
| Migration Lead | Thomas Jenkins | 100% | 10 years, AWS Migration Specialty cert |
| Security Architect | David Okafor | 75% | 14 years, CISSP, AWS Security Specialty |
| DevOps Engineers (3) | TBD | 100% each | 5+ years each |
| Database Migration Specialist | Rebecca Liu | 100% | 9 years, Oracle-to-PostgreSQL specialist |
| Application Modernisation Lead | James Park | 100% (Phase 3+) | 7 years, Kubernetes + microservices |
| QA Lead | Ana Rodriguez | 50% | 6 years, automated testing |
| Training Lead | Michael Brown | 50% (Phase 5-6) | 8 years, technical training |
| Project Manager | Sarah Walsh | 100% | 11 years, PMP, financial services |

### 7.2 Staffing Notes

- Three DevOps Engineer positions are currently designated as TBD. CloudPath will fill these positions from our bench or through targeted hiring within 4 weeks of contract signing. Candidates will have a minimum of 5 years of AWS experience and relevant certifications.
- The Security Architect (David Okafor) is allocated at 75% because he is concurrently supporting the tail end of another engagement that concludes in Month 3 of this program. He will be 100% available from Month 4 onwards.
- The Application Modernisation Lead (James Park) joins in Phase 3 to lead the refactoring workstream. During Phases 1 and 2, Chen Wei will cover modernisation planning.

### 7.3 Key Personnel Retention

CloudPath commits to retaining the named personnel (Maria Santos, Chen Wei, Thomas Jenkins, David Okafor) for the duration of the program. If any key person becomes unavailable due to circumstances beyond CloudPath's control, a replacement of equivalent or superior qualifications will be proposed within 10 business days, subject to Meridian's approval.

---

## 8. Project Timeline and Milestones

### 8.1 High-Level Timeline

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 1: Assess | 10 weeks | Month 1 | Month 2.5 |
| Phase 2: Mobilise | 6 weeks | Month 2 | Month 3.5 |
| Phase 3: Migrate Wave 1 | 12 weeks | Month 3 | Month 6 |
| Phase 4: Migrate Wave 2 | 20 weeks | Month 5 | Month 10 |
| Phase 5: Migrate Wave 3 | 24 weeks | Month 9 | Month 15 |
| Phase 6: Optimise | 16 weeks | Month 14 | Month 18 |
| Post-Migration Support | 12 months | Month 19 | Month 30 |

*Total program duration: 30 months (24-month migration + 6 months included post-migration support).*

### 8.2 Key Milestones

| Milestone | Target Date | Deliverable |
|-----------|------------|-------------|
| M1: Discovery Complete | Month 2.5 | Application portfolio assessment, wave plan |
| M2: Landing Zone Live | Month 3.5 | Production-ready AWS landing zone |
| M3: Wave 1 Complete | Month 6 | 30+ applications migrated (non-prod + Tier 3) |
| M4: Mid-Migration Review | Month 8 | Compliance gap assessment, TCO interim report |
| M5: Wave 2 Complete | Month 10 | 70+ additional applications migrated |
| M6: Dallas DC Exit Ready | Month 14 | All Dallas workloads migrated or retired |
| M7: Wave 3 Complete | Month 15 | Remaining applications migrated, modernisation complete |
| M8: Optimisation Complete | Month 18 | Cost optimisation report, training completion |
| M9: Full Handover | Month 24 | Operational handover, knowledge transfer complete |

### 8.3 Timeline Anomalies and Notes

The timeline presented above shows a total program duration of 30 months (24-month migration plus 6 months of the 12-month post-migration support period). However, the pricing section (Section 9) includes 12 months of post-migration support, which would extend the total engagement to 30 months if support begins at Month 19, but to 36 months if support begins at Month 24. The RFP requested a 24-month migration timeline. We have assumed 24 months for migration execution with post-migration support running concurrently from Month 19 onwards.

Additionally, the Dallas data centre exit target is listed as Month 14 in this section but the RFP requirement specifies Month 20. We have proposed an accelerated target but can adjust to Month 20 if preferred.

---

## 9. Pricing and Commercial Terms

### 9.1 Program Pricing Summary

| Component | Cost |
|-----------|------|
| Phase 1: Assess | $680,000 |
| Phase 2: Mobilise | $920,000 |
| Phase 3: Migrate Wave 1 | $2,100,000 |
| Phase 4: Migrate Wave 2 | $3,400,000 |
| Phase 5: Migrate Wave 3 | $3,800,000 |
| Phase 6: Optimise | $1,200,000 |
| Training Program | $450,000 |
| Post-Migration Support (12 months) | $1,650,000 |
| **Total Program Investment** | **$14,200,000** |

### 9.2 Pricing Notes

1. Pricing is based on time-and-materials with a capped maximum. If CloudPath completes the work under the cap, Meridian pays only for actual effort. If effort exceeds the cap, CloudPath absorbs the overage.
2. Travel and expenses (T&E) are estimated at $280,000 and are included in the above pricing. Actuals will be billed at cost with Meridian pre-approval for trips exceeding $5,000.
3. AWS infrastructure consumption costs are **not included** in the above pricing. Based on our preliminary TCO analysis, we estimate Meridian's AWS spend will be approximately $180,000/month in steady state, or $2.16 million annually. This is a 32% reduction from the current on-premises run rate of $3.18 million annually.
4. Third-party software licence costs (e.g., Datadog, Palo Alto) are not included. CloudPath will provide licence recommendations during Phase 1.
5. The pricing assumes a start date no later than May 1, 2026. If the start date is delayed beyond June 1, 2026, resource availability may change and pricing may need to be revised.

### 9.3 Payment Schedule

| Payment | Trigger | Amount |
|---------|---------|--------|
| 1 | Contract signing | $1,420,000 (10%) |
| 2 | M1: Discovery Complete | $1,100,000 |
| 3 | M2: Landing Zone Live | $920,000 |
| 4 | M3: Wave 1 Complete | $2,100,000 |
| 5 | M5: Wave 2 Complete | $3,400,000 |
| 6 | M7: Wave 3 Complete | $3,160,000 |
| 7 | M8: Optimisation Complete | $1,200,000 |
| 8-19 | Monthly (post-migration support) | $137,500/month |

*Payment total: $14,930,000*

### 9.4 Optional Services

| Service | Cost |
|---------|------|
| Additional penetration test (per engagement) | $45,000 |
| Extended post-migration support (per additional month) | $137,500 |
| On-site war room support during Tier 1 cutovers (per weekend) | $28,000 |
| Custom compliance report for state regulators (per report) | $15,000 |

---

## 10. Service Level Agreements

### 10.1 Migration SLAs

| Metric | Target |
|--------|--------|
| Planned cutover executed within scheduled window | 95% of cutovers |
| Successful cutover (no rollback required) | 90% of cutovers |
| Post-cutover P1 incident response time | 30 minutes |
| Post-cutover P1 incident resolution time | 4 hours |
| Hypercare availability (72 hours post-cutover) | 24/7 |

### 10.2 Post-Migration Support SLAs

| Severity | Response Time | Resolution Time |
|----------|--------------|-----------------|
| P1 (system down) | 15 minutes | 4 hours |
| P2 (degraded) | 1 hour | 8 hours |
| P3 (non-critical) | 4 hours | 5 business days |
| P4 (informational) | 1 business day | 10 business days |

### 10.3 SLA Credits

If CloudPath fails to meet the SLAs defined above in any calendar month, Meridian will receive service credits:

| SLA Miss Rate | Credit (% of monthly support fee) |
|---------------|----------------------------------|
| 1-2 misses | 5% |
| 3-5 misses | 10% |
| 6+ misses | 20% |

Maximum credit in any month: 20% of the monthly support fee ($27,500).

*Note: SLA credits are the sole and exclusive remedy for SLA failures. Credits do not apply during the first 30 days of post-migration support while baselines are being established.*

---

## 11. Risk Management

### 11.1 Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R1 | Application discovery reveals more than 140 applications | Medium | High | Include a 10% contingency buffer in wave planning. Scope increases beyond 155 applications will require a change order. |
| R2 | Third-party vendor does not support cloud deployment | Medium | Medium | Identify high-risk vendors during Phase 1. Engage vendor support early. Fallback: rehost on EC2 with current licensing. |
| R3 | Key personnel turnover | Low | High | Contractual retention commitments. Knowledge sharing across team members. 10-day replacement SLA. |
| R4 | AWS region outage during cutover | Very Low | Critical | Schedule cutovers during low-traffic windows. Multi-region DR for Tier 1 apps. Rollback plan for each cutover. |
| R5 | Data migration corruption | Low | Critical | Checksum validation at source and target. Parallel-run validation period. Automated reconciliation scripts. |
| R6 | Compliance gap discovered mid-migration | Medium | High | Mid-migration compliance assessment at Week 24. Dedicated security architect on the team. |
| R7 | Budget overrun on AWS consumption | Medium | Medium | FinOps practices from Day 1. Reserved Instances and Savings Plans purchased after 3-month baseline. Weekly cost reviews. |
| R8 | Meridian staff availability constraints | Medium | Medium | Publish workshop and interview schedules 4 weeks in advance. Provide async alternatives for data gathering. |

### 11.2 Contingency Budget

A 10% contingency ($1,420,000) is recommended but is **not included** in the proposal pricing. CloudPath recommends that Meridian reserve this amount to cover unforeseen scope changes, additional AWS consumption during parallel-run periods, or extended timelines.

---

## 12. Deliverables and Acceptance Criteria

### 12.1 Deliverables by Phase

**Phase 1: Assess**
- Application portfolio assessment report
- Migration wave plan
- TCO analysis and business case
- Risk assessment
- Network architecture design

**Phase 2: Mobilise**
- AWS landing zone (deployed and tested)
- CI/CD pipeline templates
- Security baseline configuration
- Direct Connect provisioning
- Runbook library (initial)

**Phase 3: Migrate Wave 1**
- Migrated Tier 3 applications (30+)
- Migration playbook (refined based on Wave 1 learnings)
- Performance benchmark report

**Phase 4: Migrate Wave 2**
- Migrated Tier 2 applications (70+)
- Mid-migration compliance report
- Updated TCO analysis

**Phase 5: Migrate Wave 3**
- Migrated Tier 1 applications (remaining)
- Modernised applications (containerised, deployed to EKS)
- Dallas data centre exit certification
- DR validation test results

**Phase 6: Optimise**
- Cost optimisation report and implementation
- Performance tuning report
- Training completion certificates
- Operational handover document
- Final compliance posture report

### 12.2 Acceptance Criteria

Each deliverable will be subject to a 10-business-day review period by Meridian. Deliverables are accepted when:

1. The deliverable meets the requirements specified in the applicable statement of work.
2. Meridian provides written acceptance or fails to provide feedback within the 10-business-day review period (deemed acceptance).
3. For application migrations: the application passes smoke tests, performance tests meet baseline thresholds (within 10% of on-premises performance), and no P1 issues are open at the end of the hypercare period.

### 12.3 Missing Deliverables

The following items are referenced in earlier sections but are not listed as formal deliverables:

- AWS-specific incident response playbook (referenced in Section 6.5)
- Data classification framework (referenced in Section 6.3)
- Disaster recovery test results for Tier 2 applications (Section 4.5 mentions DR for Tier 2 but only Tier 1 DR validation is listed as a Phase 5 deliverable)
- FinOps framework documentation (referenced in Risk R7)
- Vendor cloud-compatibility assessment (referenced in Risk R2)

*Note: CloudPath acknowledges these gaps and will work with Meridian during contract negotiation to determine which of these should be added as formal deliverables.*

---

## 13. References and Case Studies

### 13.1 Case Study: National Trust Bancorp

**Challenge:** National Trust Bancorp operated 95 applications across two data centres with an aging VMware infrastructure. They needed to migrate to AWS while maintaining SOC 2 and GLBA compliance.

**Solution:** CloudPath executed a 7-wave migration over 18 months using a rehost-first strategy, followed by selective modernisation of 15 customer-facing applications to EKS.

**Results:**
- 95 applications migrated with zero unplanned downtime.
- 28% reduction in infrastructure TCO.
- SOC 2 audit completed on schedule with no findings related to the migration.
- Time-to-deploy reduced from 2 weeks to 45 minutes.

**Client Quote:** "CloudPath's methodical approach gave us confidence that our migration wouldn't disrupt our operations or our compliance posture." -- CTO, National Trust Bancorp.

### 13.2 Case Study: Pacific Mutual Insurance

**Challenge:** Pacific Mutual needed a hybrid cloud strategy spanning AWS and Azure to accommodate a strategic vendor relationship requiring Azure. 62 applications needed to migrate across two clouds simultaneously.

**Solution:** CloudPath designed a unified landing zone with centralised identity, networking, and security across both clouds. The migration was completed in 14 months with 5 migration waves.

**Results:**
- 62 applications migrated (48 to AWS, 14 to Azure).
- Unified security monitoring across both clouds.
- 22% reduction in infrastructure costs.
- Successful PCI DSS re-certification during the migration.

### 13.3 Additional References

CloudPath can provide additional references from Sterling Credit Union and Atlantic Wealth Management upon request and execution of a mutual NDA.

---

## 14. Appendices

### Appendix A: Team Resumes

Full resumes for all named team members are provided in a separate document (CloudPath_Team_Resumes_MFS-2026-CM-0042.pdf).

### Appendix B: Detailed Pricing Breakdown

A line-item pricing breakdown by role, rate, and hours is provided in a separate spreadsheet (CloudPath_Pricing_Detail_MFS-2026-CM-0042.xlsx).

### Appendix C: Sample Deliverables

Sample deliverables from prior engagements (sanitised) are available upon request:
- Sample application portfolio assessment report
- Sample migration wave plan
- Sample landing zone architecture document
- Sample cost optimisation report

### Appendix D: Insurance Coverage

CloudPath maintains the following insurance coverage:
- Professional Liability / Errors & Omissions: $10,000,000 per occurrence
- Cyber Liability: $5,000,000 per occurrence
- Commercial General Liability: $2,000,000 per occurrence
- Workers' Compensation: Statutory limits

### Appendix E: Standard Terms and Conditions

CloudPath's standard Master Services Agreement (MSA) and Statement of Work (SOW) templates are enclosed as separate documents. Key terms include:

- **Intellectual Property:** All custom code, scripts, and configurations developed for Meridian during this engagement are owned by Meridian. CloudPath retains ownership of its pre-existing tools, frameworks, and methodologies.
- **Confidentiality:** Mutual NDA with a 3-year term from disclosure.
- **Limitation of Liability:** CloudPath's aggregate liability is capped at the total fees paid under the agreement.
- **Termination:** Either party may terminate with 60 days' written notice. In the event of termination, CloudPath will provide a 30-day transition assistance period at standard rates.
- **Dispute Resolution:** Binding arbitration in Travis County, Texas.

### Appendix F: AWS Well-Architected Review

CloudPath will conduct an AWS Well-Architected Review for all migrated workloads during Phase 6. The review will cover all six pillars:

1. Operational Excellence
2. Security
3. Reliability
4. Performance Efficiency
5. Cost Optimisation
6. Sustainability

Findings and recommendations will be documented in the final optimisation report.

---

*END OF PROPOSAL*

**CloudPath Solutions, LLC**  
1200 Congress Avenue, Suite 400  
Austin, TX 78701  
Contact: Maria Santos, Program Director  
Email: maria.santos@cloudpathsolutions.com  
Phone: (512) 555-0142

*This proposal is confidential and intended solely for the use of Meridian Financial Services, Inc. Reproduction or distribution without CloudPath Solutions' written consent is prohibited.*
