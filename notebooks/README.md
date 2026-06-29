# notebooks/

Exploration and visualization. Use the **"Python (fantasy-quant)"** Jupyter kernel (registered at setup).

```bash
uv run jupyter lab
```

Convention: notebooks are for *exploration and figures*, not pipeline logic — promote anything reusable
into `src/fantasy_quant/` and anything runnable into `steps/`. Clear outputs before committing (data
artifacts are gitignored).
