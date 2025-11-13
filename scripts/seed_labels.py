#!/usr/bin/env python3
import json

# Placeholder for Phase 5 seeding logic: ingest live desks, custodians, venues.
# Intentionally minimal in Phase 0.

def main():
    seeds = {
        "custodians": ["Copper", "GSR", "Anchorage"],
        "venues": ["LIQUIDNET", "SIGMA_X", "TRF"],
    }
    print(json.dumps(seeds))


if __name__ == "__main__":
    main()
