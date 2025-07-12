# Analysis Notes

## Dataset 218281 - cu_thf Model Fit

**Date**: July 12, 2025
**Analysis Type**: Combined data reflectivity fitting
**Model Used**: cu_thf
**Status**: ✅ Completed

### Fit Quality
- **Final Chi-squared**: 2.208(19)
- **Convergence**: 581 steps, 34.7 seconds
- **Quality Assessment**: Good fit (χ² < 3.0)

### Key Results
- **THF layer**: 20.9±0.7 Å interface, rho=5.97±0.01 ×10⁻⁶ Å⁻²
- **Material layer**: 62.1±0.7 Å thick, rho=5.00±0.00 ×10⁻⁶ Å⁻²
- **Cu layer**: 500.10±0.31 Å thick, rho=6.31±0.00 ×10⁻⁶ Å⁻²
- **Ti layer**: 35.78±0.18 Å thick, rho=-2.69±0.05 ×10⁻⁶ Å⁻²

### Generated Files
- `reports/fit_result_218281_cu_thf_reflectivity.svg`
- `reports/fit_result_218281_cu_thf_profile.svg`
- `reports/report_218281.md`

### Notes
- All parameters converged within reasonable ranges
- Uncertainties are well-constrained for most parameters
- Ti interface roughness has the largest relative uncertainty (±0.53 Å)
- Cu thickness is very well-determined (±0.31 Å from 500 Å)

### Tool Enhancement
- **Enhanced result_assessor.py**: Added detailed parameter table with uncertainties parsed from `problem-err.json`
- **Parameter ranges**: Added Min/Max columns showing fitting constraints from `problem-1-expt.json`
- **Improved reporting**: Now includes fit quality assessment, organized parameter tables, and analysis notes
- **Better uncertainty handling**: Uses standard deviations from MCMC sampling for robust uncertainty estimates
- **Comprehensive analysis**: Full parameter context including fitted values, uncertainties, and constraint ranges

---
