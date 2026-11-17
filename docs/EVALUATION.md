# Evaluation — synthetic-1.0

Reference: 31 October 2026. Fixed seed 420. Selected method: **Pooled gradient boosting**.

## Protocol

Training: CP-001–080, 112 weekly origins, 62,720 horizon rows; last training label 27 April, fit cutoff 30 April 2026. Validation: eight weekly origins 4 May–22 June (640 account-origins). The predeclared gate requires at least 2% lower normalized balance MAE, recall loss no greater than 3 percentage points and false-alarm-rate growth no greater than 5 percentage points. Candidate passes: validation normalized MAE 0.499 versus 0.563, recall 66.13% versus 62.90%, two false alarms for each. Default and parameters were frozen before test.

Refit: same 80 businesses, 121 weekly origins, 67,760 horizon rows, fully observable labels through 29 June; fit cutoff 30 June. Untouched tests: 13 non-overlapping seven-day origins 6 July–28 September. Known-account test measures future performance of fitted businesses; held-out CP-081–100 measures transfer to unfamiliar businesses, excluded from training and validation. Repeated businesses remain correlated; origins are not independent customer incidents.

A shortfall event means any of the next seven daily closes is strictly negative. Buffer breach is a separate event: any future close below its positive operating buffer, including negative closes. Precision = TP/(TP+FP); recall = TP/(TP+FN); false-alarm rate = FP/(FP+TN). Each business-origin contributes one event. No MAPE or uncertainty bands are used. Normalized MAE divides each origin’s mean absolute closing error by its past-56-day mean gross daily inflow plus outflow, with a minimum scale of 100 minor units; only this dimensionless statistic is pooled across currencies.

## Event results

| Split / method | Outcome | Events / origins | TP | FP | FN | TN | Precision | Recall | False-alarm rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| validation / Seasonal naive | shortfall | 62/640 (9.7%) | 39 | 2 | 23 | 576 | 95.12% | 62.90% | 0.35% |
| validation / Seasonal naive | buffer_breach | 129/640 (20.2%) | 96 | 2 | 33 | 509 | 97.96% | 74.42% | 0.39% |
| validation / Pooled gradient boosting | shortfall | 62/640 (9.7%) | 41 | 2 | 21 | 576 | 95.35% | 66.13% | 0.35% |
| validation / Pooled gradient boosting | buffer_breach | 129/640 (20.2%) | 98 | 2 | 31 | 509 | 98.00% | 75.97% | 0.39% |
| known_account_test / Seasonal naive | shortfall | 138/1040 (13.3%) | 78 | 16 | 60 | 886 | 82.98% | 56.52% | 1.77% |
| known_account_test / Seasonal naive | buffer_breach | 290/1040 (27.9%) | 192 | 12 | 98 | 738 | 94.12% | 66.21% | 1.60% |
| known_account_test / Pooled gradient boosting | shortfall | 138/1040 (13.3%) | 86 | 11 | 52 | 891 | 88.66% | 62.32% | 1.22% |
| known_account_test / Pooled gradient boosting | buffer_breach | 290/1040 (27.9%) | 212 | 18 | 78 | 732 | 92.17% | 73.10% | 2.40% |
| unseen_business_test / Seasonal naive | shortfall | 36/260 (13.8%) | 22 | 0 | 14 | 224 | 100.00% | 61.11% | 0.00% |
| unseen_business_test / Seasonal naive | buffer_breach | 74/260 (28.5%) | 54 | 1 | 20 | 185 | 98.18% | 72.97% | 0.54% |
| unseen_business_test / Pooled gradient boosting | shortfall | 36/260 (13.8%) | 22 | 2 | 14 | 222 | 91.67% | 61.11% | 0.89% |
| unseen_business_test / Pooled gradient boosting | buffer_breach | 74/260 (28.5%) | 56 | 5 | 18 | 181 | 91.80% | 75.68% | 2.69% |

## Money errors by horizon

Mean absolute errors in native currency units; each line stays within one currency. Inflow/outflow include scheduled plus remaining flows.

| Test / method | Currency | Horizon | Inflow MAE | Outflow MAE | Closing MAE |
|---|---|---:|---:|---:|---:|
| known_account_test / Seasonal naive | CHF | 1 | 1083.29 | 1749.42 | 2560.06 |
| known_account_test / Seasonal naive | CHF | 2 | 699.30 | 695.45 | 2867.12 |
| known_account_test / Seasonal naive | CHF | 3 | 1684.39 | 920.79 | 4195.81 |
| known_account_test / Seasonal naive | CHF | 4 | 713.63 | 679.92 | 4229.52 |
| known_account_test / Seasonal naive | CHF | 5 | 513.30 | 889.48 | 4801.91 |
| known_account_test / Seasonal naive | CHF | 6 | 258.17 | 3.13 | 4784.75 |
| known_account_test / Seasonal naive | CHF | 7 | 1516.15 | 582.38 | 5273.47 |
| known_account_test / Seasonal naive | EUR | 1 | 1028.69 | 1774.38 | 2508.65 |
| known_account_test / Seasonal naive | EUR | 2 | 680.23 | 650.48 | 2684.36 |
| known_account_test / Seasonal naive | EUR | 3 | 1912.04 | 867.44 | 4094.80 |
| known_account_test / Seasonal naive | EUR | 4 | 688.55 | 784.41 | 4271.35 |
| known_account_test / Seasonal naive | EUR | 5 | 355.68 | 937.61 | 4884.77 |
| known_account_test / Seasonal naive | EUR | 6 | 251.53 | 27.96 | 4896.22 |
| known_account_test / Seasonal naive | EUR | 7 | 1367.95 | 875.38 | 5594.65 |
| known_account_test / Seasonal naive | SEK | 1 | 11052.10 | 14776.69 | 22692.68 |
| known_account_test / Seasonal naive | SEK | 2 | 6374.94 | 6413.84 | 25767.26 |
| known_account_test / Seasonal naive | SEK | 3 | 16617.20 | 9173.43 | 37499.66 |
| known_account_test / Seasonal naive | SEK | 4 | 6560.30 | 5837.82 | 38144.43 |
| known_account_test / Seasonal naive | SEK | 5 | 4459.30 | 10514.69 | 46392.32 |
| known_account_test / Seasonal naive | SEK | 6 | 1657.97 | 331.24 | 45818.72 |
| known_account_test / Seasonal naive | SEK | 7 | 14750.88 | 8185.94 | 54759.87 |
| known_account_test / Pooled gradient boosting | CHF | 1 | 1080.66 | 1050.01 | 1865.39 |
| known_account_test / Pooled gradient boosting | CHF | 2 | 660.20 | 605.31 | 2086.73 |
| known_account_test / Pooled gradient boosting | CHF | 3 | 1560.72 | 871.18 | 3247.85 |
| known_account_test / Pooled gradient boosting | CHF | 4 | 659.09 | 631.75 | 3238.69 |
| known_account_test / Pooled gradient boosting | CHF | 5 | 482.70 | 523.36 | 3367.30 |
| known_account_test / Pooled gradient boosting | CHF | 6 | 259.49 | 14.08 | 3419.61 |
| known_account_test / Pooled gradient boosting | CHF | 7 | 1483.50 | 521.18 | 3844.41 |
| known_account_test / Pooled gradient boosting | EUR | 1 | 973.38 | 963.08 | 1651.05 |
| known_account_test / Pooled gradient boosting | EUR | 2 | 654.98 | 549.92 | 1782.59 |
| known_account_test / Pooled gradient boosting | EUR | 3 | 1539.79 | 768.17 | 2805.15 |
| known_account_test / Pooled gradient boosting | EUR | 4 | 639.01 | 731.08 | 2894.84 |
| known_account_test / Pooled gradient boosting | EUR | 5 | 354.42 | 503.31 | 2970.80 |
| known_account_test / Pooled gradient boosting | EUR | 6 | 252.97 | 39.77 | 3039.22 |
| known_account_test / Pooled gradient boosting | EUR | 7 | 1339.42 | 771.08 | 3565.26 |
| known_account_test / Pooled gradient boosting | SEK | 1 | 10718.48 | 9427.38 | 17435.40 |
| known_account_test / Pooled gradient boosting | SEK | 2 | 5889.67 | 5511.54 | 19974.17 |
| known_account_test / Pooled gradient boosting | SEK | 3 | 13692.00 | 8773.57 | 29539.67 |
| known_account_test / Pooled gradient boosting | SEK | 4 | 6049.95 | 5062.13 | 28918.76 |
| known_account_test / Pooled gradient boosting | SEK | 5 | 4243.44 | 5546.52 | 31660.88 |
| known_account_test / Pooled gradient boosting | SEK | 6 | 1672.48 | 453.23 | 31176.71 |
| known_account_test / Pooled gradient boosting | SEK | 7 | 14500.36 | 7515.81 | 37406.49 |
| unseen_business_test / Seasonal naive | CHF | 1 | 1005.66 | 1557.38 | 2098.62 |
| unseen_business_test / Seasonal naive | CHF | 2 | 788.49 | 747.51 | 2420.08 |
| unseen_business_test / Seasonal naive | CHF | 3 | 1724.69 | 1118.05 | 3803.56 |
| unseen_business_test / Seasonal naive | CHF | 4 | 665.16 | 532.10 | 3875.49 |
| unseen_business_test / Seasonal naive | CHF | 5 | 204.99 | 1491.99 | 5054.81 |
| unseen_business_test / Seasonal naive | CHF | 6 | 242.33 | 72.99 | 5060.32 |
| unseen_business_test / Seasonal naive | CHF | 7 | 1171.59 | 744.20 | 5652.59 |
| unseen_business_test / Seasonal naive | EUR | 1 | 770.72 | 1204.71 | 1697.83 |
| unseen_business_test / Seasonal naive | EUR | 2 | 546.92 | 523.90 | 1959.56 |
| unseen_business_test / Seasonal naive | EUR | 3 | 1630.84 | 835.64 | 3121.66 |
| unseen_business_test / Seasonal naive | EUR | 4 | 438.65 | 562.22 | 3341.28 |
| unseen_business_test / Seasonal naive | EUR | 5 | 262.19 | 874.03 | 3784.18 |
| unseen_business_test / Seasonal naive | EUR | 6 | 463.20 | 2.29 | 3704.58 |
| unseen_business_test / Seasonal naive | EUR | 7 | 1553.52 | 636.03 | 4248.90 |
| unseen_business_test / Seasonal naive | SEK | 1 | 8855.83 | 19607.23 | 25038.42 |
| unseen_business_test / Seasonal naive | SEK | 2 | 5454.89 | 10712.07 | 33690.48 |
| unseen_business_test / Seasonal naive | SEK | 3 | 23492.84 | 7797.06 | 48597.05 |
| unseen_business_test / Seasonal naive | SEK | 4 | 5974.69 | 5863.53 | 47451.37 |
| unseen_business_test / Seasonal naive | SEK | 5 | 5537.39 | 7801.03 | 53411.67 |
| unseen_business_test / Seasonal naive | SEK | 6 | 3294.10 | 30.34 | 54266.10 |
| unseen_business_test / Seasonal naive | SEK | 7 | 14011.88 | 7882.44 | 59558.41 |
| unseen_business_test / Pooled gradient boosting | CHF | 1 | 974.36 | 1110.07 | 1644.59 |
| unseen_business_test / Pooled gradient boosting | CHF | 2 | 756.88 | 639.89 | 2079.24 |
| unseen_business_test / Pooled gradient boosting | CHF | 3 | 1474.23 | 1064.66 | 3066.76 |
| unseen_business_test / Pooled gradient boosting | CHF | 4 | 656.21 | 463.16 | 3131.18 |
| unseen_business_test / Pooled gradient boosting | CHF | 5 | 215.80 | 657.58 | 3574.64 |
| unseen_business_test / Pooled gradient boosting | CHF | 6 | 243.84 | 86.26 | 3551.59 |
| unseen_business_test / Pooled gradient boosting | CHF | 7 | 1156.11 | 687.22 | 4011.18 |
| unseen_business_test / Pooled gradient boosting | EUR | 1 | 822.22 | 678.86 | 1278.17 |
| unseen_business_test / Pooled gradient boosting | EUR | 2 | 489.71 | 446.25 | 1529.83 |
| unseen_business_test / Pooled gradient boosting | EUR | 3 | 1320.21 | 647.22 | 2165.34 |
| unseen_business_test / Pooled gradient boosting | EUR | 4 | 373.92 | 515.10 | 2352.02 |
| unseen_business_test / Pooled gradient boosting | EUR | 5 | 276.52 | 516.87 | 2401.79 |
| unseen_business_test / Pooled gradient boosting | EUR | 6 | 464.49 | 14.25 | 2219.19 |
| unseen_business_test / Pooled gradient boosting | EUR | 7 | 1534.58 | 578.42 | 3011.60 |
| unseen_business_test / Pooled gradient boosting | SEK | 1 | 9363.19 | 10215.24 | 15917.35 |
| unseen_business_test / Pooled gradient boosting | SEK | 2 | 4684.61 | 8291.19 | 22723.44 |
| unseen_business_test / Pooled gradient boosting | SEK | 3 | 16412.04 | 7238.03 | 32217.83 |
| unseen_business_test / Pooled gradient boosting | SEK | 4 | 5807.72 | 5486.49 | 32640.89 |
| unseen_business_test / Pooled gradient boosting | SEK | 5 | 5536.66 | 6197.88 | 36377.26 |
| unseen_business_test / Pooled gradient boosting | SEK | 6 | 3308.15 | 141.88 | 37616.38 |
| unseen_business_test / Pooled gradient boosting | SEK | 7 | 13460.12 | 7406.40 | 41359.30 |

## Sector comparisons

Closing-balance MAE averaged over all seven horizons, separately by currency. Full event counts by sector and currency are in `evaluation/results/metrics.json`.

| Test / method | Sector | Currency | Closing MAE |
|---|---|---|---:|
| known_account_test / Seasonal naive | Consulting | CHF | 3483.68 |
| known_account_test / Seasonal naive | Consulting | EUR | 3242.73 |
| known_account_test / Seasonal naive | Consulting | SEK | 36144.12 |
| known_account_test / Seasonal naive | Logistics | CHF | 3678.01 |
| known_account_test / Seasonal naive | Logistics | EUR | 3470.32 |
| known_account_test / Seasonal naive | Logistics | SEK | 35598.80 |
| known_account_test / Seasonal naive | Manufacturing | CHF | 3093.52 |
| known_account_test / Seasonal naive | Manufacturing | EUR | 3048.83 |
| known_account_test / Seasonal naive | Manufacturing | SEK | 43926.77 |
| known_account_test / Seasonal naive | Retail | CHF | 5263.58 |
| known_account_test / Seasonal naive | Retail | EUR | 6571.62 |
| known_account_test / Seasonal naive | Retail | SEK | 51533.96 |
| known_account_test / Seasonal naive | Wholesale | CHF | 5191.89 |
| known_account_test / Seasonal naive | Wholesale | EUR | 3894.43 |
| known_account_test / Seasonal naive | Wholesale | SEK | 27562.72 |
| known_account_test / Pooled gradient boosting | Consulting | CHF | 2897.89 |
| known_account_test / Pooled gradient boosting | Consulting | EUR | 2246.31 |
| known_account_test / Pooled gradient boosting | Consulting | SEK | 25646.63 |
| known_account_test / Pooled gradient boosting | Logistics | CHF | 2667.32 |
| known_account_test / Pooled gradient boosting | Logistics | EUR | 2336.15 |
| known_account_test / Pooled gradient boosting | Logistics | SEK | 31459.06 |
| known_account_test / Pooled gradient boosting | Manufacturing | CHF | 2744.19 |
| known_account_test / Pooled gradient boosting | Manufacturing | EUR | 2337.75 |
| known_account_test / Pooled gradient boosting | Manufacturing | SEK | 31372.45 |
| known_account_test / Pooled gradient boosting | Retail | CHF | 2722.91 |
| known_account_test / Pooled gradient boosting | Retail | EUR | 3433.55 |
| known_account_test / Pooled gradient boosting | Retail | SEK | 28689.08 |
| known_account_test / Pooled gradient boosting | Wholesale | CHF | 4070.82 |
| known_account_test / Pooled gradient boosting | Wholesale | EUR | 2826.76 |
| known_account_test / Pooled gradient boosting | Wholesale | SEK | 22698.09 |
| unseen_business_test / Seasonal naive | Consulting | CHF | 2907.61 |
| unseen_business_test / Seasonal naive | Consulting | EUR | 2814.79 |
| unseen_business_test / Seasonal naive | Consulting | SEK | 37774.60 |
| unseen_business_test / Seasonal naive | Logistics | CHF | 4289.39 |
| unseen_business_test / Seasonal naive | Logistics | EUR | 3096.12 |
| unseen_business_test / Seasonal naive | Logistics | SEK | 80750.39 |
| unseen_business_test / Seasonal naive | Manufacturing | CHF | 4094.58 |
| unseen_business_test / Seasonal naive | Manufacturing | EUR | 2664.58 |
| unseen_business_test / Seasonal naive | Manufacturing | SEK | 35993.96 |
| unseen_business_test / Seasonal naive | Retail | CHF | 4088.88 |
| unseen_business_test / Seasonal naive | Retail | EUR | 4246.36 |
| unseen_business_test / Seasonal naive | Retail | SEK | 51973.33 |
| unseen_business_test / Seasonal naive | Wholesale | CHF | 4248.06 |
| unseen_business_test / Seasonal naive | Wholesale | EUR | 3125.23 |
| unseen_business_test / Seasonal naive | Wholesale | SEK | 33525.32 |
| unseen_business_test / Pooled gradient boosting | Consulting | CHF | 2945.93 |
| unseen_business_test / Pooled gradient boosting | Consulting | EUR | 1889.19 |
| unseen_business_test / Pooled gradient boosting | Consulting | SEK | 29075.87 |
| unseen_business_test / Pooled gradient boosting | Logistics | CHF | 2856.39 |
| unseen_business_test / Pooled gradient boosting | Logistics | EUR | 2469.11 |
| unseen_business_test / Pooled gradient boosting | Logistics | SEK | 50210.88 |
| unseen_business_test / Pooled gradient boosting | Manufacturing | CHF | 2170.81 |
| unseen_business_test / Pooled gradient boosting | Manufacturing | EUR | 2016.62 |
| unseen_business_test / Pooled gradient boosting | Manufacturing | SEK | 22374.02 |
| unseen_business_test / Pooled gradient boosting | Retail | CHF | 3038.43 |
| unseen_business_test / Pooled gradient boosting | Retail | EUR | 1959.07 |
| unseen_business_test / Pooled gradient boosting | Retail | SEK | 38346.80 |
| unseen_business_test / Pooled gradient boosting | Wholesale | CHF | 3504.59 |
| unseen_business_test / Pooled gradient boosting | Wholesale | EUR | 2265.65 |
| unseen_business_test / Pooled gradient boosting | Wholesale | SEK | 25206.22 |

## Failure examples

Deterministic reporting rule: the first missed shortfall and first false alarm by account ID then origin in each test, selected after scoring for diagnosis only. These cases do not affect model selection. Figures are native currency; actuals are evaluation-only.

| Test | Failure | Account / origin | Currency | Predicted minimum | Actual minimum |
|---|---|---|---|---:|---:|
| known_account_test | Missed shortfall | CP-003 / 2026-08-03 | CHF | 1257.85 | -267.54 |
| known_account_test | False alarm | CP-032 / 2026-09-21 | SEK | -10924.13 | 3814.20 |
| unseen_business_test | Missed shortfall | CP-081 / 2026-08-31 | CHF | 5160.49 | -1230.59 |
| unseen_business_test | False alarm | CP-091 / 2026-07-27 | EUR | -841.27 | 8586.18 |

## Limits and runtime

Known-account shortfall recall improves from 56.52% to 62.32%, but 52 of 138 events are still missed. Unseen recall remains 61.11%; precision falls from 100% to 91.67% because of two extra false alarms. A model is not a substitute for confirming large receipts. Late settlements, changed amounts, owner transfers and unexpected expenses can move cash outside the expected path; this report does not infer individual causes from a regression. The four app examples are computed demonstrations, not a representative test sample.

The simulator contains recurring patterns and owner contributions/distributions that stabilize some businesses. Transfer within this simulator is not external validation. No real banking data, impact study, confidence calibration, intraday payment order, available credit or FX conversion is modelled. Historical schedule mismatches are scored, not erased.

Recorded full pipeline wall time: 307.74 seconds; timings are machine-dependent. Validation prediction time 23.72 seconds, known-test 30.05 seconds, unseen-test 6.81 seconds. The interactive app loads fixed JSON and performs arithmetic only.

Reproduce with `cashpilot pipeline --output /tmp/cashpilot-full`. Compare reports with native-currency errors and the recorded selection gate; do not tune against this test set.
