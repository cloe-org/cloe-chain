<p align="center">
  <img src="docs/cloechain_banner.png" alt="cloechain banner" width="600">
</p>

# cloechain

A YAML-driven configuration and sampler runner for
[`cloelike`](https://github.com/cloe-org/cloelike) likelihoods. Point it at a
config describing a probe, its data, scale cuts, fixed/sampled parameters and
a sampler, and it runs the sampler.

Currently supported:

- **Spectroscopic probes**:
  - `GCspectro_Pls` (`cloelike.EuclidLikelihood_GCspectro_Pls`, the
    full-shape power spectrum multipoles likelihood) —
    `examples/gcspectro_pls_nautilus.yaml`.
  - `GCspectro_BAO` (`cloelike.EuclidLikelihood_GCspectro_BAO`, BAO alphas) —
    `examples/gcspectro_bao_nautilus.yaml`.
  - `GCspectro_Pls_BAO` (`cloelike.EuclidLikelihood_GCspectro_Pls_BAO`, the
    joint full-shape + BAO likelihood) —
    `examples/gcspectro_pls_bao_nautilus.yaml`.
- **Photometric probes** (angular power spectra, `cloelike.EuclidLikelihood_photo_Cls`):
  - `3x2pt` (cosmic shear + galaxy-galaxy lensing + photometric galaxy
    clustering) — `examples/3x2pt_nautilus.yaml`.
  - `WL` (cosmic shear) — `examples/wl_nautilus.yaml`.
  - `GCph`, `GGL` and `2x2pt` (GGL + GCph), configured as `3x2pt`.
- **Sampler**: [`nautilus`](https://nautilus-sampler.readthedocs.io/).

Probes, samplers and theory backends are behind small lookup tables in
`cloechain.loader` (`PROBES`, `SAMPLERS`, `BACKGROUNDS`, `PERTURBATIONS`,
`NONLINEAR_PERTURBATIONS`, `BARYON_BOOSTS`, `SPECTRO_POWERS`): adding one is a
new module plus one entry there, not a rewrite of the runner.

## Installation

`cloechain` follows the `main` branches of
[`cloelib`](https://github.com/cloe-org/cloelib),
[`cloelike`](https://github.com/cloe-org/cloelike),
[`cosmolib`](https://github.com/astro-ph/cosmolib) and
[`euclidlib`](https://github.com/euclidlib/euclidlib), plus the external
libraries of the theory model you pick (`CAMB`, `HMcode2020Emu`, `FAST-PT`
for TATT and the nonlinear galaxy bias, `COMET` or `PBJ` for the spectroscopic
multipoles, ...). The easiest way to get all of them is the `cloe-org`
environment of
[`cloe-org-environments`](https://github.com/cloe-org/cloe-org-environments).
Then, from this directory:

```bash
pip install -e .
```

## Usage

```bash
python -m cloechain --config examples/3x2pt_nautilus.yaml
```

Every example is annotated: see `examples/3x2pt_nautilus.yaml` for the
photometric options and `examples/gcspectro_pls_nautilus.yaml` for the
spectroscopic ones. File paths in `data` are relative to `data.base_directory`,
itself relative to the directory of the config file.

## Data

The examples read the synthetic data of the
[cloe-org Zenodo community](https://zenodo.org/communities/cloe-org/records),
the same files as the [playground](https://github.com/cloe-org/playground)
notebooks and scripts. By default they expect them in `../data`, next to this
repository:

| Examples | Files | Zenodo record |
|---|---|---|
| `3x2pt`, `wl` | `nz_example.fits` | [15092862](https://doi.org/10.5281/zenodo.15092862) |
| `3x2pt`, `wl` | `synthetic_coupled_cells.fits`, `mixmats_example.fits`, `covmat_2D.npz` | [19071608](https://doi.org/10.5281/zenodo.19071608) |
| `gcspectro_pls`, `gcspectro_pls_bao` | `mps_pk_*`, `cov_pk_Gauss_GCspectro_comet_*`, `mixmat_pk_*` | [18711304](https://doi.org/10.5281/zenodo.18711304) |
| `gcspectro_bao`, `gcspectro_pls_bao` | `EUC_LE3_BAO_*` | [19729182](https://doi.org/10.5281/zenodo.19729182) |
| `gcspectro_pls_bao` | `cov_pk_Gauss_GCspectro_FS+BAO_*` | [21219969](https://doi.org/10.5281/zenodo.21219969) |

For the photometric examples:

```bash
mkdir -p ../data && cd ../data
curl -LO https://zenodo.org/records/15092862/files/nz_example.fits
curl -LO https://zenodo.org/records/19071608/files/synthetic_coupled_cells.fits
curl -LO https://zenodo.org/records/19071608/files/mixmats_example.fits
curl -LO https://zenodo.org/records/19071608/files/covmat_2D.npz
```

## Photometric probes

The photometric config differs from the spectroscopic one in a few places:

- **`probe`** picks the theory model: `background`, `linear_perturbations`
  and `nonlinear_perturbations` (`CAMB`, `HMcode2020Emu`, `EE2`), an optional
  `baryon_boost` (`HMcode2020`, `FLAMINGO`) and the `mode` (`coupled` with
  the mixing matrices, or `decoupled`). `probe.settings` is passed as it is
  to the `cloelike` likelihood: `ia_model` (`NLA`, `TATT`, `null`),
  `galaxy_bias_model` (`poly`, `per_bin`, `per_bin_int`, `nonlinear`),
  `include_rsd`, `nonlinear_param_keys`, ...
- **`data`** gives the n(z) (`nz`, or `nz_positions` and `nz_shear`), the
  redshift grid they are resampled on (`z_grid`), the angular power spectra
  (`cells`), the mixing matrices (`mixing`) and the covariance (`covariance`,
  `.npz` or `.npy`, with `covariance_key` for a `.npz`). The covariance can
  cover the full 3x2pt data vector (blocks ordered WL, GGL, GCph) for any
  probe: the blocks of the probe are extracted from it.
- **`scale_cuts`** gives one multipole range per block (`WL`, `GGL`, `GCph`),
  and optionally per-spectrum ranges under `overrides`, e.g.
  `POS-SHE-1-3: [10, 300]`.
- **Per-bin parameters** are one scalar per tomographic bin in `cloelike`
  (`dz_shear_1`, ..., `b1_photo_bin0`, ...). Write them once with the `{i}`
  placeholder, in `fixed_parameters` or `sampled_parameters`:
  `dz_shear_{i}: {dist: norm, loc: 0.0, scale: 0.01}` expands to every bin,
  with the indexing `cloelike` uses for that parameter. An explicit name,
  e.g. `dz_shear_3`, overrides the template for that bin, and a template that
  matches no parameter of the likelihood is an error.
- **`data.noise_free_mock: true`** replaces the data vector with the theory
  at `fixed_parameters`, which must then hold the full fiducial point in the
  native `cloelike` parameters (`Omega_cdm0`, `As`, ...). The synthetic data
  was generated with a single model, so this is the way to get a posterior
  centred on the fiducial with any other model.

Sampling `omch2`, `ombh2`, `logA` or `h` enables their conversion to the native
parameters automatically (see `cloechain.derived_parameters`).

## Output

A run writes two files to `output.directory`, both named after
`output.name`:

- **`<name>.npz`** — the chain itself, in the same format regardless of
  which sampler produced it (see `cloechain.chain.Chain`): a 2D `samples`
  array plus a `columns` list naming them, always
  `[logweight, loglikelihood, <parameter_1>, ..., <parameter_N>]`. Load it
  with `Chain.load(path)`, or read it directly with `numpy.load`.
- **`<name>.config.yaml`** — the exact YAML config used for the run, with a
  `software_versions` block appended recording the installed version of
  `cloechain`, `cloelike`, `cloelib`, `euclidlib`, `numpy` and `scipy` at run
  time, plus whichever packages this specific run actually depends on.

## Tests

```bash
pip install -e ".[test]"
pytest
```

## Example output

![Example posterior](example_posterior.png)
