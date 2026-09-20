# GigEase (XYZ Company) — AI-Powered Parametric Income Protection Scheme
## OFFICIAL POLICY DOCUMENT & MAIN INSURANCE RULE SET

> **Policy Version**: XYZ v1.0 | 2026  
> **Policy Type**: Combined STFI (Natural Disasters) + RSMD (Social Disruptions)  
> **Target Beneficiaries**: Active Platform Delivery Partners (Food / Q-Commerce / E-Commerce: Swiggy, Zomato, Zepto, Blinkit, Amazon)  
> **Geographic Scope**: PAN India  
> **Payout Method**: Instant UPI Credit (Within 2 Hours / Target < 10 Mins)  

---

## Table of Contents
1. [Preamble & Core Vision](#1-preamble--core-vision)
2. [Definitions & Key Metrics](#2-definitions--key-metrics)
3. [Eligibility & Enrolment](#3-eligibility--enrolment)
4. [Coverage, Benefits & Payout Formula](#4-coverage-benefits--payout-formula)
5. [Premium Structure & Adjustments Chain](#5-premium-structure--adjustments-chain)
6. [Parametric Trigger Mechanism](#6-parametric-trigger-mechanism)
7. [Claim & Payout Execution Process](#7-claim--payout-execution-process)
8. [Fraud Prevention & Verification Architecture](#8-fraud-prevention--verification-architecture)
9. [Policy Exclusions](#9-policy-exclusions)
10. [Grievance Redressal & Escalation](#10-grievance-redressal--escalation)
11. [Pool Economics & Financial Reserve Rules](#11-pool-economics--financial-reserve-rules)
12. [Schedule of Rates & Proposal-cum-Policy Schedule](#12-schedule-of-rates--proposal-cum-policy-schedule)

---

## 1. Preamble & Core Vision

### 1.1 The Problem
Millions of platform-based delivery partners in India earn their livelihood on a day-to-day basis. External disruptions such as severe floods, cyclones, extreme heatwaves, pollution spikes, curfews, or local bandhs cut off their earnings by 20–30% monthly. When disruptions occur, riders face 100% financial loss with zero safety net.

### 1.2 The Solution
GigEase operates as a zero-touch parametric insurance platform. Instead of asking gig workers to prove loss through paperwork or manual claims, the system uses objective real-world data (weather APIs, NDMA alerts, traffic congestion, and verified platform earnings) to automatically detect disruptions, compute lost wages, and disburse UPI payouts directly to the worker's account.

---

## 2. Definitions & Key Metrics

- **Policyholder**: Enrolled delivery partner with an active policy.
- **Weekly Expected Income ($W_{\text{avg}}$)**: Rolling 12-week average of gross weekly earnings from the delivery platform (order pay + distance pay + waiting pay + daily bonuses + weekly target incentives).
- **Actual Weekly Income ($W_{\text{actual}}$)**: Verified weekly earnings recorded during a disruption week.
- **Trigger Threshold**: $60\%$ of $W_{\text{avg}}$. The policy triggers when $W_{\text{actual}} < 0.60 \times W_{\text{avg}}$ during a confirmed event.
- **Income Loss ($L$)**: $W_{\text{avg}} - W_{\text{actual}}$.
- **Payout Beta ($\beta$)**: Fixed payout coverage factor = **$0.70$ (70% of calculated income loss)**.
- **Coverage Amount ($C$)**: Max cumulative payout per policy period = **$1.5 \times W_{\text{avg}}$**.
- **Base Premium ($P_{\text{base}}$)**: Monthly base rate = **$5\%$ of Coverage Amount** ($3.5\%$ STFI + $1.5\%$ RSMD).
- **Incurred Claim Ratio (ICR)**: Total claims paid divided by total premiums collected (Target Range: 60% – 70%).
- **Minimum Reserve**: **30% of total active coverage** maintained in a segregated mutual pool fund before payouts execute.

---

## 3. Eligibility & Enrolment

### 3.1 Eligibility Criteria
1. **Platform Status**: Active registered delivery partner on a recognized platform.
2. **KYC Verification**: Aadhaar-verified identity via DigiLocker (only SHA-256 hash stored; raw Aadhaar never retained).
3. **Minimum Experience**: Minimum **1 month (4 weeks)** of active delivery history on the platform.
4. **Bank / Payment Account**: Valid UPI-linked bank account in the policyholder's name.
5. **Work Status**: At least 1 delivery completed in the preceding 4 weeks.

### 3.2 Policy Duration & Renewal
- **Policy Period**: 12 months (annual), auto-renewed weekly.
- **Premium Cycle**: Deducted every Monday from platform earnings.
- **Lapse Condition**: Policy lapses if worker is inactive (0 deliveries) for 8 consecutive weeks.
- **Re-enrolment**: Lapsed policies can re-enrol after a 2-week cooling-off period.

---

## 4. Coverage, Benefits & Payout Formula

### 4.1 Coverage Scope
GigEase provides a **Single Combined Policy** covering both:
1. **STFI (Natural Disasters)**: Storm, Typhoon, Flood, Inundation, Heavy Rain, Heatwave, Severe AQI Pollution, Extreme Fog.
2. **RSMD (Social Disruptions)**: Riots, Strikes, Malicious Damage, Curfews (Section 144), Bandhs, Transport Shutdowns.

> [!IMPORTANT]
> **Strict Exclusions**: Coverage is strictly limited to **LOSS OF INCOME ONLY**. Health insurance, life insurance, vehicle repairs, and medical bills are strictly excluded.

### 4.2 Payout Formula
$$\text{Loss } (L) = W_{\text{avg}} - W_{\text{actual}}$$
$$\text{Raw Payout} = \beta \times L = 0.70 \times (W_{\text{avg}} - W_{\text{actual}})$$
$$\text{Final Payout} = \min\left(\text{Raw Payout} - \text{Fraud Deductions}, \text{Coverage Amount}\right)$$

#### Worked Example:
- $W_{\text{avg}} = \text{Rs. } 4,500 / \text{week}$
- Coverage Amount ($1.5 \times W_{\text{avg}}$) = **Rs. 6,750**
- Trigger Threshold ($60\% \times W_{\text{avg}}$) = **Rs. 2,700**
- $W_{\text{actual}}$ during flood week = **Rs. 1,106**
- Trigger Check: $\text{Rs. } 1,106 < \text{Rs. } 2,700 \implies$ **TRIGGERED**
- Loss = $\text{Rs. } 4,500 - \text{Rs. } 1,106 = \text{Rs. } 3,394$
- Raw Payout ($70\% \times 3,394$) = **Rs. 2,375**
- **Final UPI Credit = Rs. 2,375** (processed in under 2 hours / 10 minutes target)

---

## 5. Premium Structure & Adjustments Chain

### 5.1 Weekly Premium Calculation Steps
Computed every Sunday night for all active policies:
1. **$W_{\text{avg}}$**: Rolling 12-week average gross weekly income.
2. **Coverage**: $1.5 \times W_{\text{avg}}$.
3. **Monthly Base Premium**: $5\% \times \text{Coverage}$ ($3.5\%$ STFI + $1.5\%$ RSMD).
4. **Weekly Base Premium**: $\text{Monthly Base Premium} / 4$.
5. **AI Risk Adjustment**: $\times (1 + \text{AI Zone Risk Score}, 0 \text{ to } 0.5)$.
6. **Seasonal Loading**: $\times (1 + \text{Zone Seasonal Factor})$.
7. **No Claim Discount (NCD)**: $\times (1 - \text{NCD}\%)$.
8. **Claim Loading**: $\times (1 + \text{Claim Loading}\%)$.

### 5.2 Seasonal Premium Loading (STFI)
Auto-applied 4 weeks before high-risk seasons:
- **Chennai (Velachery / Tambaram / Pallikaranai)**: +30% to +50% (Oct–Jan flood season)
- **Chennai (Mylapore / Elevated zones)**: +10% to +20%
- **Delhi NCR (Connaught Place / Heat islands)**: +15% to +25% (May–Jul heatwave season)
- **Off-season / Low-risk zones**: 0%

### 5.3 No Claim Discount (NCD) & Claim Loading Schedules
- **NCD Rate**: 2% cumulative discount per clean week (capped at 20% max discount).
- **NCD Reset**: Resets to 0% immediately following any settled claim.
- **Claim Loading Schedule** (within rolling 4-week window):
  - 1 Claim: **+5% surcharge**
  - 2 Claims: **+12% surcharge**
  - 3+ Claims: **+25% surcharge + manual review**
  - 8 consecutive clean weeks: **Resets loading to 0%**

---

## 6. Parametric Trigger Mechanism

### 6.1 STFI Parametric Thresholds (Primary Zone Level)
An event is confirmed if **ANY** of the following thresholds are met:
- **Rainfall**: $> 80 \text{ mm in 24 hours}$ (Source: OpenWeatherMap, IMD)
- **Wind Speed**: $> 50 \text{ km/h sustained}$ (Source: OpenWeatherMap)
- **Flood Alert Level**: $\ge \text{Level 2}$ on NDMA scale 0–4 (Source: NDMA Feed)
- **Cyclone Warning**: Any active warning issued (Source: IMD Cyclone Division)
- **Visibility**: $< 50 \text{ metres}$ (Source: OpenWeatherMap)
- **Heat Index**: $> 45^\circ\text{C}$ heatwave declared (Source: IMD + OpenWeatherMap)

### 6.2 RSMD Dual-Source Confirmation Logic
Social disruption events require confirmation from **AT LEAST 2 of the 4 independent sources**:
1. **NewsAPI / GNews**: Keywords (bandh, curfew, strike) + city match (3+ articles in 2 hrs).
2. **NDMA Alert Feed**: `emergency_alert = True`.
3. **Google Maps Traffic API**: City-wide congestion index $> 0.85$ (gridlock).
4. **Govt / Police Order**: Section 144 or official curfew declaration.

---

## 7. Claim & Payout Execution Process

### 7.1 Automated 13-Step Execution Workflow
1. Disruption event confirmed by environmental/news feeds.
2. All workers in affected zones identified.
3. Policy active status & eligibility verified.
4. $W_{\text{actual}}$ retrieved from platform API.
5. Trigger condition evaluated: $W_{\text{actual}} < 0.60 \times W_{\text{avg}}$.
6. Loss computed: $L = W_{\text{avg}} - W_{\text{actual}}$.
7. Raw Payout computed ($70\% \times L$).
8. AI Fraud Model executes GPS, hardware, and behavioral anomaly scoring.
9. Payout capped at Coverage Amount.
10. Pool balance checked against 30% Minimum Reserve Rule.
11. Instant UPI transfer executed via Razorpay API.
12. WhatsApp & FCM Push notifications sent to worker.
13. Claim ledger updated; NCD/loading schedule adjusted.

---

## 8. Fraud Prevention & Verification Architecture

### 8.1 Multi-Layer Fraud Signals & Weights
| Check Category | Signal / Method | Fraud Score Weight |
| :--- | :--- | :--- |
| **Hardware / Location** | Android `is_mocked_location` flag = True | **+0.60** |
| | Zone-Weather Mismatch (Claimed flood zone, but API shows dry) | **+0.80** |
| | Accelerometer vs GPS Mismatch (Stationary motion sensor vs moving GPS) | **+0.50** |
| | Speed $> 120 \text{ km/h}$ on bike | **+0.45** |
| | Location Jump $> 5 \text{ km}$ in $< 2 \text{ mins}$ | **+0.40** |
| | Cell Tower Mismatch $> 2 \text{ km}$ from claimed GPS | **+0.35** |
| | IP Geolocation Mismatch $> 5 \text{ km}$ (non-VPN) | **+0.25** |
| **Behavioral Anomaly** | Order Acceptance Rate drops $< 30\%$ in claim week | Suspicious |
| | Active hours during event = 0, yet claiming | Suspicious |
| | Claim Frequency $> 3$ in 4 weeks | Suspicious |
| **Syndicate / Collusion** | Zone claim spike $> 3\times$ historical average | Paused & Flagged |
| | Synchronized submission (10+ workers in $<5$ mins) | Cluster Flagged |
| | Shared Device / IP at registration | Hard Flagged |

### 8.2 Fraud-Based Decision Matrix
| Fraud Score | System Action | Payout & Rider Experience |
| :--- | :--- | :--- |
| **$< 0.30$** | **Auto-Approve** | **100% instant UPI payout** within 2 hours (Target < 10 mins). |
| **$0.30 \text{ to } 0.50$** | **Soft Flag** | **50% paid immediately**; 50% held for 48-hr review (WhatsApp location selfie verification). |
| **$0.50 \text{ to } 0.70$** | **Hard Flag** | Full payout held; human review team decision within 7 days. |
| **$> 0.70$** | **Reject** | Claim denied with plain-English explanation; 30-day appeal window. |

> [!NOTE]
> **Fairness Rule**: Degraded GPS signal or poor accuracy (e.g. $\pm 120\text{m}$) during heavy rain/cyclones is expected due to atmospheric attenuation. It is weighted in the worker's favor (treated as lower risk, not higher).

---

## 9. Policy Exclusions

1. **Voluntary Absence**: Unexplained absence without prior active delivery status before the event.
2. **Platform Suspension**: Account suspension or termination by the platform for misconduct or policy violations.
3. **Personal Health / Accident**: Medical expenses, illness, injury, or vehicle repairs (strictly excluded).
4. **Pre-Existing Low Performance**: Average weekly income below Rs. 500 in the 4 weeks before the event.
5. **Technical / Platform Outages**: Internal app changes not caused by natural or social events.
6. **Deliberate Income Suppression**: Refusing orders within 48 hours prior to an event to artificially lower $W_{\text{actual}}$.

---

## 10. Grievance Redressal & Escalation Matrix

| Level | Authority | Resolution Time |
| :--- | :--- | :--- |
| **L1** | In-App / WhatsApp Support | 48 hours |
| **L2** | Claims Review Officer | 7 working days |
| **L3** | Head of Claims, GigEase | 15 working days |
| **L4** | Insurance Ombudsman (IRDAI) | Statutory IRDAI timelines |

---

## 11. Pool Economics & Financial Rules

1. **Mutual Risk Pool Model**: Premiums from all enrolled workers are pooled into a segregated fund from which claims are paid.
2. **Minimum Reserve Rule**: At all times, **30% of total active coverage** must remain in the pool fund. If breached, payouts are queued (max 7 days) and drawn in the next collection cycle or reinsurance layer.
3. **ICR Target Range (60% – 70%)**:
   - **ICR $< 50\%$**: Over-profitable. Reduce base loading; increase NCD discount rate to 3%/week.
   - **ICR $50\% \text{ to } 70\%$**: Target zone. No changes required.
   - **ICR $70\% \text{ to } 85\%$**: Increase base lambda by 0.5%; tighten fraud threshold by 0.05.
   - **ICR $> 85\%$**: Alert admin dashboard; suspend new enrolments; trigger manual ICR review.

---

## 12. Schedule of Rates

### 12.1 Weekly Premium Rate Schedule by $W_{\text{avg}}$
| $W_{\text{avg}}$ (Rs./week) | Coverage Amount (Rs.) | Base Monthly Premium (Rs.) | Base Weekly Premium (Rs.) |
| :--- | :--- | :--- | :--- |
| **1,000 to 1,999** | 1,500 to 2,998 | 75 to 150 | 19 to 37 |
| **2,000 to 2,999** | 3,000 to 4,498 | 150 to 225 | 37 to 56 |
| **3,000 to 3,999** | 4,500 to 5,998 | 225 to 300 | 56 to 75 |
| **4,000 to 4,999** | 6,000 to 7,498 | 300 to 375 | **75 to 94** ($\sim\text{Rs. } 84/\text{wk}$ for $W_{\text{avg}} = 4,500$) |
| **5,000 to 5,999** | 7,500 to 8,998 | 375 to 450 | 94 to 112 |
| **6,000 and above** | 9,000 and above | 450 and above | 112 and above |

---

### Authoritative Rule Confirmation
This document serves as the **Canonical Main Policy Rule Set** for all financial, parametric trigger, fraud detection, and pool reserve computations within the GigEase platform.
