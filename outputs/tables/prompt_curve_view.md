# Prompt Curve Translation View — German DA Power (DE_LU)

**Model data through:** 2026-05-04 23:00 UTC+02:00  
**Generated:** 2026-05-04 23:46 UTC

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
| Prompt Week | 94.89 | 76.00 | +18.89 | +2.07σ | **LONG** | High |
| Prompt Month | 58.08 | 45.00 | +13.08 | +2.09σ | **LONG** | High |

**Prompt Week — Desk Action**  
Instrument: EEX prompt-week baseload forward | Position: **LONG**  
Rationale: Model fair value (94.89 €/MWh) is 18.89 €/MWh above the illustrative forward (76.00 €/MWh). Buy the EEX prompt-week baseload forward to capture the 18.89 €/MWh edge on delivery-period settlement.  
Sizing: Full-size position — edge exceeds 1.96σ; model error unlikely to eliminate the edge.

**Prompt Month — Desk Action**  
Instrument: EEX prompt-month baseload forward | Position: **LONG**  
Rationale: Model fair value (58.08 €/MWh) is 13.08 €/MWh above the illustrative forward (45.00 €/MWh). Buy the EEX prompt-month baseload forward to capture the 13.08 €/MWh edge on delivery-period settlement.  
Sizing: Full-size position — edge exceeds 1.96σ; model error unlikely to eliminate the edge.

---

## Scenario 2: Market Neutral
*Market roughly agrees with the model — forward near fair value*

| Period | Fair Value (€/MWh) | Forward (€/MWh) | Edge (€/MWh) | σ-multiple | Direction | Confidence |
|--------|-------------------|----------------|-------------|-----------|-----------|------------|
| Prompt Week | 94.89 | 95.00 | -0.11 | -0.01σ | FLAT | Noise |
| Prompt Month | 58.08 | 58.00 | +0.08 | +0.01σ | FLAT | Noise |

**Prompt Week — Desk Action**  
Instrument: EEX prompt-week baseload forward | Position: **FLAT**  
Rationale: Edge of -0.11 €/MWh (-0.01σ) is within noise threshold. Model does not provide sufficient conviction to deviate from flat.  
Sizing: No position. Revisit if the forward moves more than 1.28σ from fair value.

**Prompt Month — Desk Action**  
Instrument: EEX prompt-month baseload forward | Position: **FLAT**  
Rationale: Edge of +0.08 €/MWh (0.01σ) is within noise threshold. Model does not provide sufficient conviction to deviate from flat.  
Sizing: No position. Revisit if the forward moves more than 1.28σ from fair value.

---

## Scenario 3: Market Bullish
*Market overprices fundamentals — forward well above model fair value*

| Period | Fair Value (€/MWh) | Forward (€/MWh) | Edge (€/MWh) | σ-multiple | Direction | Confidence |
|--------|-------------------|----------------|-------------|-----------|-----------|------------|
| Prompt Week | 94.89 | 107.00 | -12.11 | -1.33σ | **SHORT** | Moderate |
| Prompt Month | 58.08 | 68.00 | -9.92 | -1.58σ | **SHORT** | Moderate |

**Prompt Week — Desk Action**  
Instrument: EEX prompt-week baseload forward | Position: **SHORT**  
Rationale: Model fair value (94.89 €/MWh) is 12.11 €/MWh below the illustrative forward (107.00 €/MWh). Sell the EEX prompt-week baseload forward to capture the 12.11 €/MWh edge on delivery-period settlement.  
Sizing: Half-size position — edge exceeds 1.28σ; meaningful conviction but room for model error.

**Prompt Month — Desk Action**  
Instrument: EEX prompt-month baseload forward | Position: **SHORT**  
Rationale: Model fair value (58.08 €/MWh) is 9.92 €/MWh below the illustrative forward (68.00 €/MWh). Sell the EEX prompt-month baseload forward to capture the 9.92 €/MWh edge on delivery-period settlement.  
Sizing: Half-size position — edge exceeds 1.28σ; meaningful conviction but room for model error.

---

## Invalidation Conditions

The following conditions apply to all scenarios. Any of these would materially impair the reliability of the model's fair-value estimate:

- **weather_surprise:** A sustained heat wave or cold snap drives load or renewable output outside the climatological range used for the recursive forecast. Climatological proxies cannot anticipate weather regimes.
- **nuclear_outage:** A surprise nuclear outage in Germany or France reduces cross-border import capacity, shifting the supply stack and repricing scarcity.
- **gas_repricing:** A gas supply disruption (TTF spike) raises the marginal cost of gas-fired generation, lifting the price floor above model assumptions.
- **model_assumption_breakdown:** Sigma bands are derived from OOF residuals over the Jul 2025–May 2026 period. If the future regime differs materially (e.g. structural demand shift, new interconnector capacity), uncertainty is underestimated.
- **demand_response:** Large-scale industrial curtailment or demand response not captured by the ENTSO-E load proxy suppresses realized demand below the forecast.
