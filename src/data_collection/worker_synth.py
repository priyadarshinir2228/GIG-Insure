"""Synthetic delivery-partner roster used to seed the live platform (real platform rosters are proprietary)."""
import numpy as np
from faker import Faker

from giginsure.data import PERSONAS

PERSONA_MIX = {"food": 0.5, "qcom": 0.3, "ecom": 0.2}
BANKS = ["okaxis", "oksbi", "okhdfcbank", "ybl", "paytm", "ibl"]


def synth_workers(zone_ids, n=60, seed=21):
    fake = Faker("en_IN"); Faker.seed(seed)
    rng = np.random.RandomState(seed)
    out = []
    for i in range(n):
        persona = rng.choice(list(PERSONA_MIX), p=list(PERSONA_MIX.values()))
        name = fake.first_name() + " " + fake.last_name()
        handle = "".join(ch for ch in name.lower() if ch.isalpha())[:12] + str(rng.randint(10, 99))
        out.append(dict(worker_id=f"GW{i + 1:04d}", name=name, persona=str(persona), zone_id=int(rng.choice(zone_ids)),
                        upi=f"{handle}@{rng.choice(BANKS)}",
                        hourly_rate=round(PERSONAS[persona]["rate"] * rng.normal(1, 0.04), 2)))
    return out
