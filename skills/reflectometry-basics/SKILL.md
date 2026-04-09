---
name: reflectometry-basics
description: >
  Domain primer on neutron reflectometry — what it measures, how to interpret
  results, and quality metrics. USE FOR: understanding physical meaning of
  parameters, interpreting fit quality, explaining results to users.
  DO NOT USE FOR: running tools (see fitting, partial-assessment skills).
---

# Neutron Reflectometry Basics

## What Neutron Reflectometry Measures

[TODO: human to fill — brief explanation of specular neutron reflectometry, what physical properties it probes (density/composition profiles at interfaces), and typical applications]

## Scattering Length Density (SLD) Profiles

[TODO: human to fill — what SLD is, how it relates to material composition, how a layer model maps to an SLD profile vs depth, and what the SLD profile tells you about the sample]

## Data Columns: Physical Meaning

| Column | Symbol | Physical Meaning |
|--------|--------|-----------------|
| Q | Momentum transfer | $Q = \frac{4\pi}{\lambda}\sin\theta$ — relates to the length scale probed. Higher Q = shorter length scales (finer features). Units: 1/Å |
| R | Reflectivity | Fraction of incident neutrons reflected at each Q value. Ranges from ~1 at low Q (total reflection) to very small values at high Q. Dimensionless |
| dR | Uncertainty | Statistical uncertainty on R from counting statistics. Used as weights in fitting. Dimensionless |
| dQ | Resolution | Instrument Q resolution (FWHM). Arises from beam divergence and wavelength spread. Smears sharp features in R(Q). Units: 1/Å |

## Layer Model Concepts

[TODO: human to fill — explain the slab model approximation, what thickness/roughness/SLD mean physically, how the Parratt recursion or matrix method calculates R(Q) from a layer stack, and the role of interface roughness]

## Interpreting Fit Quality

### Chi-squared ($\chi^2$)

The reduced chi-squared measures how well the model fits the data:

$$\chi^2 = \frac{1}{N} \sum_i \frac{(R_i^{\text{data}} - R_i^{\text{model}})^2}{(\delta R_i)^2}$$

| $\chi^2$ range | Assessment | Action |
|----------------|------------|--------|
| < 2.0 | Excellent | Fit is good; review parameter uncertainties |
| 2.0 – 3.0 | Good | Acceptable; check for systematic residual patterns |
| 3.0 – 5.0 | Acceptable | Consider adjusting model (add/remove layers, widen ranges) |
| > 5.0 | Poor | Model likely needs revision — wrong layer structure or data issues |

### Partial Data Overlap Quality

When checking overlap between partial curves (different angular settings), the overlap chi-squared is:

$$\chi^2_{\text{overlap}} = \frac{1}{N} \sum_i \frac{(R_1 - R_2^{\text{interp}})^2}{\sigma_1^2 + \sigma_2^2}$$

| $\chi^2_{\text{overlap}}$ | Assessment |
|---------------------------|------------|
| < 1.5 | Good overlap |
| 1.5 – 3.0 | Acceptable |
| > 3.0 | Poor — investigate data quality |

## Common Materials and SLD Values

[TODO: human to fill — table of common materials used in these experiments (Si, Cu, Ti, THF, D2O, H2O, etc.) with their neutron SLD values in units of 10⁻⁶ Å⁻²]

## Fitting Strategy

[TODO: human to fill — practical guidance on: which parameters to fix vs fit, how to set sensible parameter ranges, when to add or remove layers, how to interpret parameter correlations, and common pitfalls]
