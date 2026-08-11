"""The probe extension point: one module per supported likelihood class.

Available: `gcspectro_pls`, `gcspectro_bao`, `gcspectro_pls_bao`.

A new probe module must expose `obs_labels(cfg)`, `build_likelihood(cfg)`,
`vector_parameter_names(likelihood)`, `loglike(likelihood, parameters)`,
`tracked_packages(cfg)`, and be registered in `cloechain.loader.PROBES`.
"""
