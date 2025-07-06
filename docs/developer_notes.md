# Developer Notes

## Tools

### `create_temporary_model.py`

This tool allows for the creation of temporary models with adjusted parameter ranges. It takes a base model, a new model name, and a list of parameter adjustments as input. It then creates a new model file with the specified adjustments.

**Example:**

```bash
python3 tools/create_temporary_model.py cu_thf cu_thf_temp --adjust Cu thickness 500,800
```
