# Binary Beta explanation

This is stipulated evidence impact, not calibrated truth probability.

Validation passed: True. Policy: `binary-beta-v1`.

## Supplied evidence

| ID | Cluster | Relation | Mass | Disposition |
| --- | --- | --- | --- | --- |
| a-000 | shared | supports | 0.75 | contributing |
| b-000 | shared | supports | 0.75 | contributing |
| c-000 | opposing | contradicts | 0.5 | contributing |
| d-000 | old | contradicts | 9.0 | withdrawn |
| e-000 | pending | supports | 4.0 | Not eligible in this supplied snapshot |
| f-000 | zero | supports | 0.0 | contributing |

## Cluster contributions

| Cluster | Evidence IDs | Raw + / − | Effective + / − | Multipliers + / − |
| --- | --- | --- | --- | --- |
| opposing | c-000 | 0.0 / 0.5 | 0.0 / 0.5 | 0.0 / 1.0 |
| shared | a-000, b-000 | 1.5 / 0.0 | 1.0 / 0.0 | 0.6666666666666666 / 0.0 |
| zero | f-000 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

## Readout

Each sign is capped separately at 1.0 per cluster.
Raw masses are the sums of eligible input masses for that cluster and sign.
Effective masses are capped raw masses; multipliers are effective/raw
(zero when raw mass is zero). Zero-mass records retain provenance.
Withdrawn and excluded records add no mass; withdrawal takes precedence.

`alpha = 1.0 + 1.0 = 2.0`; `beta = 1.0 + 0.5 = 1.5`.
`mean = alpha / (alpha + beta) = 4/7`; `variance = alpha × beta / ((alpha + beta)² × (alpha + beta + 1)) = 8/147`.
`strength = 1.0 + 0.5 = 1.5`; concentration includes the prior: `3.5`.
`opposing_mass = min(effective_support, effective_contradiction) = 0.5`; `conflict_balance = 2 × opposing_mass / strength = 0.6666666666666666` (zero when strength is zero).
5 active links include 1 excluded; 1 withdrawn links are disjoint from both.
4 IDs contribute, including any zero-mass records.

Exact recorded readout (also checked against rational arithmetic):

```json
{
  "proposition_id": "p",
  "dynamics_version": "binary-beta-v1",
  "policy": {
    "version": "binary-beta-v1",
    "alpha0": 1.0,
    "beta0": 1.0,
    "cluster_cap": 1.0
  },
  "alpha": 2.0,
  "beta": 1.5,
  "mean": 0.5714285714285714,
  "variance": 0.054421768707482984,
  "evidence_strength": 1.5,
  "posterior_concentration": 3.5,
  "raw_support": 1.5,
  "raw_contradiction": 0.5,
  "effective_support": 1.0,
  "effective_contradiction": 0.5,
  "conflict_balance": 0.6666666666666666,
  "opposing_mass": 0.5,
  "active_count": 5,
  "withdrawn_count": 1,
  "excluded_count": 1,
  "evidence_ids": [
    "a-000",
    "b-000",
    "c-000",
    "f-000"
  ],
  "withdrawn_ids": [
    "d-000"
  ],
  "exclusions": [
    [
      "e-000",
      "Not eligible in this supplied snapshot"
    ]
  ],
  "clusters": [
    {
      "cluster_id": "opposing",
      "evidence_ids": [
        "c-000"
      ],
      "raw_support": 0.0,
      "raw_contradiction": 0.5,
      "effective_support": 0.0,
      "effective_contradiction": 0.5,
      "support_multiplier": 0.0,
      "contradiction_multiplier": 1.0
    },
    {
      "cluster_id": "shared",
      "evidence_ids": [
        "a-000",
        "b-000"
      ],
      "raw_support": 1.5,
      "raw_contradiction": 0.0,
      "effective_support": 1.0,
      "effective_contradiction": 0.0,
      "support_multiplier": 0.6666666666666666,
      "contradiction_multiplier": 0.0
    },
    {
      "cluster_id": "zero",
      "evidence_ids": [
        "f-000"
      ],
      "raw_support": 0.0,
      "raw_contradiction": 0.0,
      "effective_support": 0.0,
      "effective_contradiction": 0.0,
      "support_multiplier": 0.0,
      "contradiction_multiplier": 0.0
    }
  ]
}
```

Explicit exclusion is a pure-projector input; current workspace APIs do not
persist this exclusion mechanism. This example does not add that capability.
