# Data sources

Real platform earnings, rosters and claim records are proprietary, and the DEVTrails 2026 problem statement
allows mock / simulated weather, traffic, platform and payment integrations. Every dataset is therefore
generated with fixed seeds so all reported numbers can be reproduced exactly.

| Dataset | Generator | Size | Used for |
|---|---|---|---|
| Weekly pricing table | `giginsure.data.generate_weekly` (seed 42) | 156 weeks x 40 zones x 3 personas = 18,720 rows | premium model, drift replay |
| Claims with telemetry | `giginsure.data.generate_claims` (seed 11) | 30,000 claims, 6% fraud (GPS spoofing, fake presence, claim farming) | fraud model |
| Hourly weather | `giginsure.data.generate_hourly_weather` (seed 5) | 10 zones x 365 days x 24 h = 87,600 rows, ground truth + noisy sensors | trigger evaluation |
| Live feed (mock) | `data_collection.env_collector.MockWeather` | 1 reading / zone / simulated hour | live trigger monitor |
| Live feed (real) | Open-Meteo weather + air-quality APIs (`GIGINSURE_WEATHER=openmeteo`) | 15-minute cache per zone | live trigger monitor |
| Partner roster | `data_collection.worker_synth` (Faker en_IN, seed 21) | 60 partners across `config/zones.yaml` | live platform seed |

Seasonal structure encoded in the generators: south-west (week ~31) and north-east (week ~45) monsoon rainfall
peaks, a summer heat peak (week ~18) and a winter air-quality peak (weeks ~48-1).

Note: Open-Meteo reports US AQI, which is on a different scale from India's CPCB AQI; treat the AQI trigger in
`openmeteo` mode as indicative.
