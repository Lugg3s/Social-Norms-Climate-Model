# Social Norms Climate Model

This repository contains the computational model developed as part of a Master's thesis. It investigates how social norms and peer influence can affect climate-mitigation behaviour and its interaction with a climate/emissions model.

## Contents

- `agent.py` — agent-based social-norm layer and peer interactions
- `model_equations.py` — climate and behavioural model equations and scenario handling
- `batch_runner.py` — batch simulations
- `main.ipynb` — main notebook for running and exploring the model
- `plotting.py` — visualisation utilities
- `make_plot_videos.py` — generation of plot videos
- `scenarios.json` — model parameter scenarios
- `global.1751_2017.csv` — emissions data used by the model

## Status

The code is part of ongoing Master's thesis research and is therefore subject to change.

## Reproducibility

The model is implemented primarily in Python and uses NumPy, pandas, SciPy, and Jupyter notebooks. Parameter scenarios are defined in `scenarios.json`.
