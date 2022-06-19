# Python Interface to the International Statistical Classification of Diseases and Related Health Problems

[![license badge](https://img.shields.io/badge/license-MIT-blue.svg?style=flat)][license file]
[![ICD-10 badge](https://img.shields.io/badge/ICD--10-%F0%9F%97%B8%20done-green.svg?style=flat)][ICD-10]
[![ICD-10-CM badge](https://img.shields.io/badge/ICD--10--CM-%F0%9F%97%B8%20done-green.svg?style=flat)][ICD-10-CM]
[![ICD-11 badge](https://img.shields.io/badge/ICD--11-%E2%9C%97%20not%20yet-red.svg?style=flat)][ICD-11]
![tests badge](https://github.com/rmnldwg/icd/actions/workflows/tests.yml/badge.svg?style=flat)
[![docs badge](https://github.com/rmnldwg/icd/actions/workflows/docs.yml/badge.svg?style=flat)](https://rmnldwg.github.io/icd)
[![codecov](https://codecov.io/gh/rmnldwg/icd/branch/main/graph/badge.svg?token=53LOK18GLT)](https://codecov.io/gh/rmnldwg/icd)


[license file]: https://github.com/rmnldwg/icd/blob/main/LICENSE
[ICD-10]: https://icd.who.int/browse10
[ICD-10-CM]: https://www.cdc.gov/nchs/icd/icd10cm.htm
[ICD-11]: https://icd.who.int/browse11

***

## Content

1. [Disclaimer](#disclaimer)
2. [Installation](#installation)
3. [Usage](#usage)
   1. [Chapters](#chapters)
   2. [Blocks](#blocks)
   3. [Category](#category)
   4. [Exploration](#exploration)
4. [Motivation](#motivation)
5. [Roadmap](#roadmap)

***

## Disclaimer

⚠️ This is not an official tool from the WHO, the CDC or any other authority with respect to clinical classifications. This Python package is independently developed and maintainaned. It should therefore probably not be used in critical clinical applications as it wasn't approved or cross-checked by the issuers of the classifications.

***

## Installation

This package has not yet been pushed to PyPI, so it can't just be installed via pip. Instead, clone the repository, `cd` into the directory and install it
locally.

```bash
git clone git@github.com/rmnldwg/icd.git
cd icd
pip install .
```

***

## Usage

📖 **DOCS:** The full documentation is hosted [here][docs] using GitHub pages.

[docs]: https://rmnldwg.github.io/icd

To get started, import the package and load a codex. The ICD-10 codex can be loaded from the submodule `rev10`, while the clinical modification of the CDC, ICD-10-CM, is available in `rev10cm`:

```python
import icd

icd10_codex = icd.rev10.get_codex(release="2019")
icd10cm_codex = icd.rev10cm.get_codex(release="2022")
```

### Chapters

The created objects are both root nodes of the respective ICD tree. Directy under that, it contains the main chapters of the classification, which are accessible via a dictionary aptly named `chapters`. The dictionary's keys are the codes of the chapters and the values the respective entry instance. For example

```python
icd10_codex.chapters["IX"]
```

returns

```text
ICD10Chapter('IX', 'Diseases of the circulatory system')
```

⚠️ **NOTE:** There is also an attribute called `chapter`. But that attribute returns the current entry's chapter, which is either the entry itself, if it *is* a chapter, or the chapter under which the entry is grouped. This is a general pattern: The singular form (`root`, `chapter`, `block`) returns the grouping *above* the current entry, while the plural form (`chapters`, `blocks`, `categories`) return dictionaries with keys of ICD codes and values of children elements *below*.

### Blocks

Next in the ICD hierarchy are blocks, for which the `code` attribute is a range of ICD codes, like `C00-C96`. The blocks of a chapter are accessible from a chapter via `blocks` in the same manner as chapters are accessed from the root.

```python
icd10_codex.chapters["II"].blocks["C00-C97"]
```

returns

```text
ICD10Block(code='C00-C97', title='Malignant neoplasms')
```

Blocks may contain other blocks. So it is possible for a block element to have both the attributes `block` and `blocks` available. E.g. the block with the code `C00-C75` is such a case:

```python
middle_block = codex.get("C00-C75")
parent_block = middle_block.block    # parent block will have the code range `C00-C97`
child_blocks = moddle_block.blocks   # dictionary containing all the blocks immediately below
```

### Category

Blocks themselves can have either yet more, but finer, blocks as children (reach them via the `blocks` attribute again) or categories containing actual diagnoses. In the latter case - you might have guessed it - they are returned in a dictionary with codes as keys called `categories`.

```python
icd10_codex.chapters["XVI"].blocks["P05-P08"].categories["P07"]
```

returns

```text
ICD10Category(code='P07', title='Disorders related to short gestation and low birth weight, not elsewhere classified')
```

### Exploration

Of course, one doesn't know the chapters, blocks and codes by heart. Which is why there are a growing number of utilities to explore and visualize the tree of codes. Frist, the entire subtree of an entry can be plotted up to a specified depth using the `tree(maxdepth=<N>)` method:

```python
icd10_codex.chapters["XII"].blocks["L10-L14"].tree()
```

returns

```text
block L10-L14: Bullous disorders
├───category L10: Pemphigus
│   ├───category L10.0: Pemphigus vulgaris
│   ├───category L10.1: Pemphigus vegetans
│   ├───category L10.2: Pemphigus foliaceus
│   ├───category L10.3: Brazilian pemphigus [fogo selvagem]
│   ├───category L10.4: Pemphigus erythematosus
│   ├───category L10.5: Drug-induced pemphigus
│   ├───category L10.8: Other pemphigus
│   └───category L10.9: Pemphigus, unspecified
├───category L11: Other acantholytic disorders
│   ├───category L11.0: Acquired keratosis follicularis
│   ├───category L11.1: Transient acantholytic dermatosis [Grover]
│   ├───category L11.8: Other specified acantholytic disorders
│   └───category L11.9: Acantholytic disorder, unspecified
├───category L12: Pemphigoid
│   ├───category L12.0: Bullous pemphigoid
│   ├───category L12.1: Cicatricial pemphigoid
│   ├───category L12.2: Chronic bullous disease of childhood
│   ├───category L12.3: Acquired epidermolysis bullosa
│   ├───category L12.8: Other pemphigoid
│   └───category L12.9: Pemphigoid, unspecified
├───category L13: Other bullous disorders
│   ├───category L13.0: Dermatitis herpetiformis
│   ├───category L13.1: Subcorneal pustular dermatitis
│   ├───category L13.8: Other specified bullous disorders
│   └───category L13.9: Bullous disorder, unspecified
└───category L14: Bullous disorders in diseases classified elsewhere
```

It is also possible to search for codes or even just parts of codes using the `search()` method. It always returns a list of found entries.

```python
# get category by ICD code
cat = icd10_codex.search("C32.1")[0]

# print ancestry of category
cat.ancestry()
```

The `ancestry()` function prints out the ancestors of a given entry, in contrast to the `tree()`, which prints the descendants. The above code will output this:

```text
root ICD-10 root: International Statistical Classification of Diseases and Related Health Problems 10th Revision
└───chapter II: Neoplasms
    └───block C00-C97: Malignant neoplasms
        └───block C00-C75: Malignant neoplasms, stated or presumed to be primary, of specified sites, except of lymphoid, haematopoietic and related tissue
            └───block C30-C39: Malignant neoplasms of respiratory and intrathoracic organs
                └───category C32: Malignant neoplasm of larynx
                    └───category C32.1: Supraglottis
```

Finally, it's possible to check if a specific code exists using the `exists(code)` method and return it using `get(code)`:

```python
icd10_codex.exists("H26.2")  # will return `True`
icd10_codex.get("H26.2")     # will return the respective category
```

***

## Motivation

I recently noticed that there have been some attempts to write a Python package for dealing with [ICD](https://www.who.int/standards/classifications/classification-of-diseases) codes, notably the python package [`icd10-cm`](https://github.com/bryand1/icd10-cm) which is very simple and pythonic, as well as the [`icd-codex`](https://github.com/icd-codex/icd-codex), which was apparently the result of a hackathon and represents the ICD 10 codes as a graph.

Despite those attempts however, there is no package out there that would serve all needs or even just simply deal with the latest 11th revision of ICD. On one hand this might be because the WHO is actually quite stingy with the raw data. If it publishes any data openly at all it is usually some reduced table in a somewhat unconventional format (for programmers and data scientists).

This package attempts to combine the great ideas of the previously mentioned packages but provide a more complete interface to the ICD system.

***

## Roadmap

As one might have noticed, this package isn't the complete interface to the ICD system it strives to be. So, here's an outlook of what features are planned to be added soon:

- [ ] Implementation of the latest revision ICD-11 ([issue #7])
- [ ] A translation from ICD-10 to ICD-11 and back ([issue #8])
- [ ] Adding modifiers to ICD-10 ([issue #3])
- [ ] Enable exporting the codex in different formats ([issue #6])

[issue #3]: https://github.com/rmnldwg/icd/issues/3
[issue #6]: https://github.com/rmnldwg/icd/issues/6
[issue #7]: https://github.com/rmnldwg/icd/issues/7
[issue #8]: https://github.com/rmnldwg/icd/issues/8

Stay tuned for updates!
