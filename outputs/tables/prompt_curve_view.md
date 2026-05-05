# Prompt Curve Translation View — German DA Power (DE_LU)

**Model data through:** 2026-05-04 23:00 UTC+02:00  
**Generated:** 2026-05-05 06:02 UTC

> **Disclaimer:** Forward prices are illustrative hypothetical reference levels,
> not real market quotes. Included solely to demonstrate the DA-to-curve
> translation methodology across long, neutral, and short signal regimes.

---

## Confidence Framework

| Level    | Threshold            | Desk Implication                         |
|----------|----------------------|------------------------------------------|
| High     | edge ≥ 1.96σ        | Full-size position                       |
| Moderate | 1.28σ ≤ edge < 1.96σ | Half-size position                       |
| Low      | 0.50σ ≤ edge < 1.28σ | Quarter-size — indicative only           |
| Noise    | edge < 0.50σ        | Flat — insufficient conviction to trade  |

---

## Scenario 1: Market Bearish
*Market underprices fundamentals — forward well below model fair value*

| Period | Fair Value (€/MWh) | Forward (€/MWh) | Edge (€/MWh) | σ-multiple | Direction | Confidence |
|--------|-------------------|----------------|-------------|-----------|-----------|------------|
| Prompt Week | 100.02 | 76.00 | +24.02 | +2.63σ | **LONG** | High |
| Prompt Month | 64.10 | 45.00 | +19.10 | +3.05σ | **LONG** | High |

**Prompt Week — Desk Action**  
Instrument: EEX prompt-week baseload forward | Position: **LONG**  
Rationale: Model fair value (100.02 €/MWh) is 24.02 €/MWh above the illustrative forward (76.00 €/MWh). Buy the EEX prompt-week baseload forward to capture the 24.02 €/MWh edge on delivery-period settlement.  
Sizing: Full-size position — edge exceeds 1.96σ; model error unlikely to eliminate the edge.

**Prompt Month — Desk Action**  
Instrument: EEX prompt-month baseload forward | Position: **LONG**  
Rationale: Model fair value (64.10 €/MWh) is 19.10 €/MWh above the illustrative forward (45.00 €/MWh). Buy the EEX prompt-month baseload forward to capture the 19.10 €/MWh edge on delivery-period settlement.  
Sizing: Full-size position — edge exceeds 1.96σ; model error unlikely to eliminate the edge.

---

## Scenario 2: Market Neutral
*Market roughly agrees with the model — forward near fair value*

| Period | Fair Value (€/MWh) | Forward (€/MWh) | Edge (€/MWh) | σ-multiple | Direction | Confidence |
|--------|-------------------|----------------|-------------|-----------|-----------|------------|
| Prompt Week | 100.02 | 95.00 | +5.02 | +0.55σ | **LONG** | Low |
| Prompt Month | 64.10 | 58.00 | +6.10 | +0.97σ | **LONG** | Low |

**Prompt Week — Desk Action**  
Instrument: EEX prompt-week baseload forward | Position: **LONG**  
Rationale: Model fair value (100.02 €/MWh) is 5.02 €/MWh above the illustrative forward (95.00 €/MWh). Buy the EEX prompt-week baseload forward to capture the 5.02 €/MWh edge on delivery-period settlement.  
Sizing: Quarter-size position — edge exceeds 0.50σ; treat as indicative, not a conviction trade.

**Prompt Month — Desk Action**  
Instrument: EEX prompt-month baseload forward | Position: **LONG**  
Rationale: Model fair value (64.10 €/MWh) is 6.10 €/MWh above the illustrative forward (58.00 €/MWh). Buy the EEX prompt-month baseload forward to capture the 6.10 €/MWh edge on delivery-period settlement.  
Sizing: Quarter-size position — edge exceeds 0.50σ; treat as indicative, not a conviction trade.

---

## Scenario 3: Market Bullish
*Market overprices fundamentals — forward well above model fair value*

| Period | Fair Value (€/MWh) | Forward (€/MWh) | Edge (€/MWh) | σ-multiple | Direction | Confidence |
|--------|-------------------|----------------|-------------|-----------|-----------|------------|
| Prompt Week | 100.02 | 107.00 | -6.98 | -0.76σ | **SHORT** | Low |
| Prompt Month | 64.10 | 68.00 | -3.90 | -0.62σ | **SHORT** | Low |

**Prompt Week — Desk Action**  
Instrument: EEX prompt-week baseload forward | Position: **SHORT**  
Rationale: Model fair value (100.02 €/MWh) is 6.98 €/MWh below the illustrative forward (107.00 €/MWh). Sell the EEX prompt-week baseload forward to capture the 6.98 €/MWh edge on delivery-period settlement.  
Sizing: Quarter-size position — edge exceeds 0.50σ; treat as indicative, not a conviction trade.

**Prompt Month — Desk Action**  
Instrument: EEX prompt-month baseload forward | Position: **SHORT**  
Rationale: Model fair value (64.10 €/MWh) is 3.90 €/MWh below the illustrative forward (68.00 €/MWh). Sell the EEX prompt-month baseload forward to capture the 3.90 €/MWh edge on delivery-period settlement.  
Sizing: Quarter-size position — edge exceeds 0.50σ; treat as indicative, not a conviction trade.

---

## Invalidation Conditions

The following conditions apply to all scenarios. Any of these would materially impair the reliability of the model's fair-value estimate:

- **weather_surprise:** A sustained heat wave or cold snap drives load or renewable output outside the climatological range used for the recursive forecast. Climatological proxies cannot anticipate weather regimes.
- **nuclear_outage:** A surprise nuclear outage in Germany or France reduces cross-border import capacity, shifting the supply stack and repricing scarcity.
- **gas_repricing:** A gas supply disruption (TTF spike) raises the marginal cost of gas-fired generation, lifting the price floor above model assumptions.
- **model_assumption_breakdown:** Sigma bands are derived from OOF residuals over the Jul 2025–May 2026 period. If the future regime differs materially (e.g. structural demand shift, new interconnector capacity), uncertainty is underestimated.
- **demand_response:** Large-scale industrial curtailment or demand response not captured by the ENTSO-E load proxy suppresses realized demand below the forecast.
