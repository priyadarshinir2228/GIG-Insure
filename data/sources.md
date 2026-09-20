# Data Sources & Attribution Log — GigEase MLOps Stage 1

**Generated Date**: 2026-09-17 22:03:17  
**Project**: GigEase — AI-Powered Parametric Income Protection Platform for Swiggy Delivery Partners  
**Author**: PRIYADARSHINI R (24AD0222 | Batch 126)

---

## 1. Stream 1 — Environmental & Disruption Data
- **Source Name**: Open-Meteo Weather Reanalysis API & Forecast Engine
- **URL**: [https://open-meteo.com](https://open-meteo.com)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Pull Date**: 2026-09-17
- **Parameters Pulled**: Precipitation (`rainfall_mm`), Max Temp (`temperature_celsius`), Wind Speed (`wind_speed_kmph`), Weather Code (`WMO`).
- **Secondary Source**: CPCB Real-Time AQI API (data.gov.in) & OpenAQ (`openaq`)
- **Holiday Calendar**: Python `holidays` library (`holidays.India(subdiv='KA')`)

---

## 2. Stream 2 — Worker & Persona Data
- **Structural Reference**: Kaggle Zomato Delivery Operations Analytics Dataset
- **URL**: [https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset](https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset)
- **License**: Open Data Commons Attribution (ODC-By)
- **Income Benchmark Source**: IDinsight DERII Study (Gig Worker Wages in Urban India)
- **Cited Values**: Baseline hourly rate = ₹102/hr (Metro), ₹82/hr (Tier-2); 32% expense ratio; ₹18,761/month net earnings.
- **Generator Tools**: `Faker` (en_IN) + SDV `GaussianCopulaSynthesizer` for PII-safe hashed IDs (`worker_id`).

---

## 3. Stream 3 — Platform & Order Data
- **Source Structure**: Swiggy Delivery Partner Order Log Stream & Mock Platform API
- **License**: Synthetic Platform Stream (Proprietary Hackathon Simulator)
- **Aggregation Grain**: Weekly per-worker totals key `(worker_id, zone_id, week_start_date)`.
- **Fields Logged**: `orders_completed`, `orders_cancelled`, `baseline_expected_weekly_income`, `actual_weekly_earnings`, `earnings_loss_amount`.

---

## 4. Stream 4 — Claims & Fraud Signal Data
- **Source Structure**: Rule-Based Synthetic Fraud Anomaly Injector
- **License**: Internal Hackathon Proof-of-Work Generator
- **Fraud Patterns Injected**:
  1. **GPS Deviation**: Distances >15km from active zone during disruption.
  2. **Syndicate Device Sharing**: Clusters >3 workers sharing hashed `device_id`.
  3. **Timing Anomaly**: Claims submitted >12 hours after disruption event window.
- **Labels**: `is_fraud_label` (Supervised training ground truth).
