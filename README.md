# International Classification of Disease

## Motivation

I recently noticed that there have been some attempts to write a Python package for dealing with [ICD](https://www.who.int/standards/classifications/classification-of-diseases) codes, notably the python package [`icd10-cm`](https://github.com/bryand1/icd10-cm) which is very simple and pythonic, as well as the [`icd-codex`](https://github.com/icd-codex/icd-codex), which was apparently the result of a hackathon and represents the ICD 10 codes as a graph.

Despite those attempts however, there is no package out there that would serve all needs or even just simply deal with the latest 11th revision of ICD. On one hand this might be because the WHO is actually quite stingy with the raw data. If it publishes any data openly at all it is usually some reduced table in a somewhat unconventional format (for programmers and data scientists).

This package attempts to combine the great ideas of the previously mentioned packages but provide a more complete interface to the ICD system.