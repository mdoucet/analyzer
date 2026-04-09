---
name: models
description: >
  Refl1d model files for neutron reflectometry fitting — how they work,
  available models, and how to create or modify them. USE FOR: choosing a model,
  understanding model structure, creating new models, adjusting parameter ranges.
  DO NOT USE FOR: running fits (see fitting skill) or data organization.
---

# Reflectometry Models

## What Is a Model File?

A model file is a Python module in the `models/` directory that defines a function:

```python
def create_fit_experiment(q, dq, data, errors):
    """
    Parameters
    ----------
    q : array — Momentum transfer values (1/Å)
    dq : array — Q resolution, FWHM (1/Å)
    data : array — Measured reflectivity R
    errors : array — Uncertainty on R (dR)

    Returns
    -------
    refl1d.experiment.Experiment
    """
```

The function builds a layer model using refl1d's `SLD`, `Slab`, and `Experiment` classes, sets parameter ranges for fitting, and returns an `Experiment` object.

## Layer Model Structure

Models define a sample as a stack of layers separated by `|`, ordered from top (incident medium) to bottom (substrate):

```python
from refl1d.names import *

THF = SLD("THF", rho=5.8)
Si = SLD("Si", rho=2.07)
Ti = SLD("Ti", rho=-1.2)
Cu = SLD("Cu", rho=6.25)
material = SLD(name="material", rho=5, irho=0.0)

sample = THF(0, 11.4) | material(58, 13) | Cu(505, 4.6) | Ti(39.5, 9.1) | Si
#        ^incident       ^layers...                                         ^substrate
```

Each `SLD(thickness, interface)` call creates a slab. Parameters are constrained with `.range(min, max)`:

```python
sample["material"].thickness.range(10.0, 200.0)
sample["material"].material.rho.range(5.0, 12.0)
sample["material"].interface.range(1.0, 33.0)
```

## Available Models

| Model | Description | Layers |
|-------|-------------|--------|
| `cu_thf` | Standard Cu/THF electrochemical cell | THF \| material \| Cu \| Ti \| Si |
| `cu_thf_no_oxide` | Same without oxide layer | THF \| Cu \| Ti \| Si |
| `cu_thf_tiny` | Minimal variant (thin material, fewer free params) | THF \| material \| Cu \| Ti \| Si |
| `ionomer_sld_1` | Ionomer model variant 1 | [TODO: describe layers] |
| `ionomer_sld_2` | Ionomer model variant 2 | [TODO: describe layers] |
| `ionomer_sld_3` | Ionomer model variant 3 | [TODO: describe layers] |

## Creating a New Model

1. **Copy an existing model** as a starting point:
   ```bash
   cp models/cu_thf.py models/my_model.py
   ```
2. Edit the layer structure and parameter ranges
3. The model is immediately available by name (`my_model`) in all tools

## Generating Standalone Fit Scripts

The `create-model` command combines a model with a data file into a self-contained Python script:

```bash
create-model cu_thf REFL_218281_combined_data_auto.txt
# → creates model_218281_cu_thf.py
```

This is useful for running fits outside the analyzer framework or for debugging.

## Adjusting Parameter Ranges

The `create-temporary-model` command creates a modified copy of a model with different parameter ranges:

```bash
create-temporary-model cu_thf cu_thf_wide --adjust 'Cu thickness 300,1000'
```

This creates `models/cu_thf_wide.py` with the Cu thickness range changed to [300, 1000]. The `--adjust` flag format is:

```
--adjust 'LAYER_NAME PARAMETER MIN,MAX'
```

Multiple adjustments can be specified:

```bash
create-temporary-model cu_thf cu_thf_custom \
  --adjust 'Cu thickness 300,1000' \
  --adjust 'material rho 2,8'
```
