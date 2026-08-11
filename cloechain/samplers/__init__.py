"""Sampler backends. Only `nautilus` is implemented today.

Each sampler module exposes:

- `run(loglike_fn, priors, sampler_settings, run_settings=None)`,
  returning the raw `(points, logweight, loglikelihood)` arrays -- turning
  those into a `cloechain.chain.Chain` and saving it happens centrally in
  `runner.py`, not here, so the on-disk chain format never depends on which
  sampler produced it.
- `TRACKED_PACKAGES`, the package(s) whose version matters when this sampler
  is chosen (e.g. `("nautilus-sampler",)`) -- see `cloechain.versions`.

See `cloechain.loader.SAMPLERS` for how a run is dispatched to one by name
from the config's `sampler.kind` key.
"""
