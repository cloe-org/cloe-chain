# cloechain

A YAML-driven configuration and sampler runner for
[`cloelike`](https://github.com/cloe-org/cloelike) likelihoods. Point it at a
config describing a probe, its data, scale cuts, fixed/sampled parameters and
a sampler, and it runs the sampler.

Currently supported:

- **Probes**:
  - `GCspectro_Pls` (`cloelike.EuclidLikelihood_GCspectro_Pls`, the
    full-shape power spectrum multipoles likelihood) —
    `examples/gcspectro_pls_nautilus.yaml`.
  - `GCspectro_BAO` (`cloelike.EuclidLikelihood_GCspectro_BAO`, BAO alphas
    only, no bias/RSD model) — `examples/gcspectro_bao_nautilus.yaml`.
  - `GCspectro_Pls_BAO` (`cloelike.EuclidLikelihood_GCspectro_Pls_BAO`, the
    joint full-shape + BAO likelihood) —
    `examples/gcspectro_pls_bao_nautilus.yaml`.
- **Sampler**: [`nautilus`](https://nautilus-sampler.readthedocs.io/).

Both are behind small lookup tables in `cloechain.loader` (`PROBES` /
`SAMPLERS`) — adding another probe or sampler is a new module plus one entry
there, not a rewrite of the runner.

## Installation

`cloechain` depends on `cloelike`, `cloelib` and `euclidlib`, which are not on
PyPI — install those first:

```bash
pip install git+https://github.com/cloe-org/cloelib.git
pip install git+https://github.com/cloe-org/cloelike.git
pip install git+https://github.com/euclidlib/euclidlib.git
```

then:

```bash
pip install -e .
```

## Usage

```bash
python -m cloechain --config examples/gcspectro_pls_nautilus.yaml
```

See `examples/gcspectro_pls_nautilus.yaml` for a full annotated example. The
config has these top-level sections:

- `probe`: which likelihood class to build (`kind`, one of `GCspectro_Pls`,
  `GCspectro_BAO`, `GCspectro_Pls_BAO`), plus the `Background` (`background`,
  e.g. `CAMB`) to use -- a keyword looked up in `cloechain.loader.BACKGROUNDS`.
  `GCspectro_Pls`/`GCspectro_Pls_BAO` also need `SpectroPower`
  (`spectro_power`, a `{code, rsd_model}` pair, e.g.
  `{code: COMET, rsd_model: EFT}` -- `rsd_model` is always required
  explicitly, even for a code that currently has only one registered
  model, e.g. `{code: PBJ, rsd_model: EFT}`), a keyword looked up in
  `cloechain.loader.SPECTRO_POWERS`; `GCspectro_BAO` has no bias/RSD model
  at all, so it skips `spectro_power` entirely. `Perturbations` (needed by
  `PBJ`, and always by `GCspectro_BAO`) is resolved automatically from
  `background` via `cloechain.loader.PERTURBATIONS` -- nothing to configure.
- `data`: redshift bins and `euclidlib` filename templates (`{}` placeholder,
  resolved relative to the config file via `base_directory`). `covariance` is
  always required (its content depends on the probe: full-shape-only,
  BAO-only, or the joint full-shape+BAO covariance with cross-terms -- but
  there is always exactly one). `mixing` is optional
  (`GCspectro_Pls`/`GCspectro_Pls_BAO` only). The data-vector template is
  split by observable instead of a single generic key: `datavec_FS` (required
  by `GCspectro_Pls`/`GCspectro_Pls_BAO`) and `datavec_BAO` (required by
  `GCspectro_BAO`/`GCspectro_Pls_BAO`) -- each probe validates the one(s) it
  needs are present. Two independent redshift-label conventions are used to
  fill in each template's `{}` (see `cloechain.config.DataConfig`):
  `datavec_FS`/`covariance`/`mixing` use trailing-zero-stripped labels (`1.0`
  -> `"1."`), while `datavec_BAO` uses plain `str(z)` (`1.0` -> `"1.0"`) --
  matching the official Euclid BAO product naming (see
  `examples/gcspectro_pls_bao_nautilus.yaml`).
- `scale_cuts` (optional, default none): per-redshift, per-multipole
  `[min, max]` cuts in h/Mpc; keys are redshift values and must match
  `data.redshifts` exactly, one entry per bin. Required by
  `GCspectro_Pls`/`GCspectro_Pls_BAO` (they raise a clear error in its
  absence); meaningless for `GCspectro_BAO` (BAO alphas aren't a function
  of scale), so just omit it there.
- `fixed_parameters`: default values for every parameter not being sampled.
- `sampled_parameters`: one entry per free parameter, always
  `{dist: <name>, ...kwargs}` — `flat` is our alias for a uniform
  prior given as `min`/`max`; any other name is a `scipy.stats` distribution
  looked up by that name, with the remaining kwargs passed straight through
  (e.g. `norm` takes `loc`/`scale`). No `bins` marker needed: for a name the
  probe expects as one array entry per redshift bin (e.g. `b1`), a plain
  spec is broadcast identically to every bin; a per-bin entry that differs
  by redshift can instead be given either as a list (`[{...}, {...}, ...]`,
  one spec per bin in `data.redshifts` order) or as a dict keyed by redshift
  value (`{1.0: {...}, 1.2: {...}, ...}`, like `scale_cuts`) — both free to
  differ from each other, including in distribution family — see `NP0` in
  `examples/gcspectro_pls_nautilus.yaml`. `{dist: AM, loc: mean, scale: std}`
  is a special case for a per-bin entry: instead of being drawn by the
  sampler, that bin's parameter is analytically marginalised (Gaussian
  prior `mean`/`std`) via `EuclidLikelihood_GCspectro_Pls.loglike_AM` -- it
  can be a plain spec broadcast to every bin (like `cnlo` below, if the same
  prior applies everywhere) or one of the per-bin forms above (like `bGam3`
  below, whose fiducial differs by redshift), and a per-bin list/dict is
  free to mix `AM` entries with normally-sampled ones (see `bGam3`/`cnlo` in
  `examples/gcspectro_pls_nautilus.yaml`).
- `sampler`: `kind: nautilus` plus `settings` (passed straight through as
  `nautilus.Sampler(...)` keyword arguments: `n_live`, `filepath`, `pool`,
  `resume`, ...) and optional `run_settings` (passed to `sampler.run()`:
  `f_live`, `n_eff`, `timeout`, ...).
- `output`: `directory`/`name` for the saved chain.
- `derived_parameters` (optional): map of registered relation names to
  `true`/`false`, e.g. `{bG2_coevolution: true}`. Every enabled one is
  applied, *in `derived_parameters` insertion order*, right after the flat
  sample is reassembled into the full parameter dict, *before* constraints
  or the likelihood -- fixing one parameter as a function of others
  already in that dict. A parameter driven this way should be dropped from
  both `fixed_parameters` and `sampled_parameters` (any value given there
  is simply overwritten, wasting a sampled dimension if it was also listed
  as free). Registered relations fall into two groups:
  - **Bias relations** (explicit opt-in only, no auto-detection -- see
    below): the Lagrangian coevolution relations `bG2 = -2/7 * (b1 - 1)`
    (`bG2_coevolution`) and `bGam3 = -1/6 * (b1 - 1) - 5/2 * bG2`
    (`bGam3_coevolution`), and the excursion-set fit
    `bG2 = 0.524 - 0.547*b1 + 0.046*b1^2` (`bG2_excursion_set`, an
    alternative to `bG2_coevolution` -- enabling both just means whichever
    is listed last wins, both set `bG2`), all per redshift bin. Insertion
    order matters when one relation reads a parameter another one sets:
    `bGam3_coevolution` needs `bG2` already final, so a `bG2_*` relation
    enabling `bGam3_coevolution` too must be listed first.
  - **Cosmological reparametrizations**, for sampling/fixing a parameter in
    a form other than the one `cloelib`/`cloelike` accept directly:
    `H0 = 100*h` (`H0_from_h`), `Omega_cdm0 = omch2 / h**2`
    (`Omega_cdm0_from_omch2`), `Omega_b0 = ombh2 / h**2`
    (`Omega_b0_from_ombh2`, both with `h = H0 / 100`), and
    `As = exp(logA) * 1e-10` (`As_from_logA`, the inverse of
    `logA = ln(1e10 * As)`). These are **auto-enabled**: just put `h`/
    `omch2`/`ombh2`/`logA` in `fixed_parameters`/`sampled_parameters`
    instead of `H0`/`Omega_cdm0`/`Omega_b0`/`As`, and the matching relation
    is turned on with no `derived_parameters` entry needed (an explicit
    `true`/`false` there still overrides the auto-detected value, if you
    ever need to). No ordering constraint between them: if sampling `h`
    instead of `H0`, `Omega_cdm0_from_omch2`/`Omega_b0_from_ombh2` read `h`
    directly rather than needing `H0_from_h` to have already set `H0`.

  See `cloechain.loader.DERIVED_PARAMETERS` for the full registry, and
  `cloechain.derived_parameters` for the implementations (add a relation to
  both, giving its entry a `"trigger"` in `cloechain.loader.DERIVED_PARAMETERS`
  only if it has an unambiguous stand-in name, to register a new one).
- `constraints` (optional): map of registered constraint names to `true`/
  `false`, e.g. `{negative_w0_wa_sum: true}`. Every enabled one is checked
  (combined with AND), right after `derived_parameters`, before every
  likelihood evaluation, rejecting a point outright (as `-inf`) *before*
  the (expensive) likelihood is even called -- for joint cuts across
  parameters that can't be expressed as an independent per-parameter prior
  (e.g. `w0 + wa <= 0`). See `cloechain.loader.CONSTRAINTS` for the
  registered names, and `cloechain.constraints` for their implementations
  (add your own to both to register a new one).

## Output

A run writes two files to `output.directory`, both named after
`output.name`:

- **`<name>.npz`** — the chain itself, in the same format regardless of
  which sampler produced it (see `cloechain.chain.Chain`): a 2D `samples`
  array plus a `columns` list naming them, always
  `[logweight, loglikelihood, <parameter_1>, ..., <parameter_N>]`. Load it
  with `Chain.load(path)`, or read it directly with `numpy.load`.
- **`<name>.config.yaml`** — the exact YAML config used for the run,
  verbatim, with a `software_versions` block appended recording the
  installed version of `cloechain`, `cloelike`, `cloelib`, `euclidlib`,
  `numpy` and `scipy` at run time, plus whichever packages this *specific*
  run actually depends on: the sampler chosen in `sampler.kind` (e.g.
  `nautilus-sampler` -- each sampler module declares its own
  `TRACKED_PACKAGES`) and the physics engine(s) this run's `background`/
  `spectro_power` choice depends on (e.g. `camb`, `comet-emu` -- see
  `Probe.tracked_packages`). None of these are fixed for every run -- they
  depend on what was actually chosen in the config. The config alone
  doesn't pin any of these, and a different version of e.g. `cloelike`
  or `comet-emu` can change the physics for the same config. Still valid
  YAML, so it can be passed straight back to `--config` to reproduce the run.
