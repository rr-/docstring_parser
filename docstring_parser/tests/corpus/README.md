# Docstring corpus

`docstrings.json` holds docstrings extracted, unmodified, from the source code
of the projects below by `scripts/build_corpus.py`. They are only used as test
data. Each docstring remains under the license of the project it comes from.

| Project | Version | License |
| --- | --- | --- |
| numpy | 2.5.4 | BSD-3-Clause |
| scipy | 1.18.1 | BSD-3-Clause |
| pandas | 3.0.6 | BSD-3-Clause |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| matplotlib | 3.11.2 | Matplotlib License (PSF-based) |
| jax | 0.11.2 | Apache-2.0 |
| keras | 3.15.1 | Apache-2.0 |
| rich | 15.0.0 | MIT |
| absl-py | 2.5.1 | Apache-2.0 |
| google-auth | 2.61.0 | Apache-2.0 |
| transformers | 5.20.2 | Apache-2.0 |
| PyTorch | 2.14.1 | BSD-3-Clause |
| requests | 2.34.2 | Apache-2.0 |
| Werkzeug | 3.1.9 | BSD-3-Clause |
| click | 8.5.0 | BSD-3-Clause |
| SQLAlchemy | 2.1.6 | MIT |
| boto3 | 1.43.118 | Apache-2.0 |
| Sphinx | 9.1.0 | BSD-2-Clause |
| Twisted | 26.4.0 | MIT |
| pydoctor | 25.10.1 | MIT |
| CPython standard library | 3.12 | PSF-2.0 |

`expected_legacy.json.gz` and `expected.json.gz` are the recorded parse
results; see `test_corpus.py`.
