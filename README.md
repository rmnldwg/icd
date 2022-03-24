# Python Interface to the International Statistical Classification of Diseases and Related Health Problems

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

To get started, import the package and load a codex. The ICD-10 codex can be loaded from the submodule `rev10`, while the clinical modification of the CDC, ICD-10-CM, is available in `rev10cm`:

```python
import icd

icd10_codex = icd.rev10.get_codex(release="2019")
icd10cm_codex = icd.rev10cm.get_codex(release="2022")
```

### Chapters

The created objects are both root nodes of the respective ICD tree. Directy 
under that, it contains the main chapters of the classification, which are 
accessible via a dictionary aptly named `chapter`

```python
icd10_codex.chapter["IX"]
```

returns

```text
ICD10Chapter(code='IX', title='Diseases of the circulatory system', revision='10')
```

### Blocks

Next in the ICD hierarchy are blocks, for which the `code` attribute is a range of ICD codes, like `"C00-C96"`. The blocks of a chapter are accessible from a chapter via `block` in the same manner as chapters are accessed from the root.

```python
icd10_codex.chapter["II"].block["C00-C97"]
```

returns

```text
ICD10Block(code='C00-C97', title='Malignant neoplasms', revision='10')
```

### Category

Blocks themselves can have either yet more, but finer, blocks as children (reach them via the `block` attribute again) or categories containing actual diagnoses. In the latter case - you might have guessed it - they are returned in a dictionary with codes as keys called `category`.

```python
icd10_codex.chapter["XVI"].block["P05-P08"].category["P07"]
```

returns

```text
ICD10Category(code='P07', title='Disorders related to short gestation and low birth weight, not elsewhere classified', revision='10')
```

### Exploration

Of course, one doesn't know the chapters, blocks and codes by heart. Which is why there are a growing number of utilities to explore and visualize the tree of codes. Frist, the entire subtree of an entry can be plotted up to a specified depth using the `tree(maxdepth=<N>)` method:

```python
print(icd10_codex.chapter["XII"].tree(maxdepth=2))
```

returns

```text
block L00-L08: Infections of the skin and subcutaneous tissue
├───category L00: Staphylococcal scalded skin syndrome
├───category L01: Impetigo
│   ├───category L01.0: Impetigo [any organism] [any site]
│   └───category L01.1: Impetiginization of other dermatoses
├───category L02: Cutaneous abscess, furuncle and carbuncle
│   ├───category L02.0: Cutaneous abscess, furuncle and carbuncle of face
│   ├───category L02.1: Cutaneous abscess, furuncle and carbuncle of neck
│   ├───category L02.2: Cutaneous abscess, furuncle and carbuncle of trunk
│   ├───category L02.3: Cutaneous abscess, furuncle and carbuncle of buttock
│   ├───category L02.4: Cutaneous abscess, furuncle and carbuncle of limb
│   ├───category L02.8: Cutaneous abscess, furuncle and carbuncle of other sites
│   └───category L02.9: Cutaneous abscess, furuncle and carbuncle, unspecified
├───category L03: Cellulitis
│   ├───category L03.0: Cellulitis of finger and toe
│   ├───category L03.1: Cellulitis of other parts of limb
│   ├───category L03.2: Cellulitis of face
│   ├───category L03.3: Cellulitis of trunk
│   ├───category L03.8: Cellulitis of other sites
│   └───category L03.9: Cellulitis, unspecified
├───category L04: Acute lymphadenitis
│   ├───category L04.0: Acute lymphadenitis of face, head and neck
│   ├───category L04.1: Acute lymphadenitis of trunk
│   ├───category L04.2: Acute lymphadenitis of upper limb
│   ├───category L04.3: Acute lymphadenitis of lower limb
│   ├───category L04.8: Acute lymphadenitis of other sites
│   └───category L04.9: Acute lymphadenitis, unspecified
├───category L05: Pilonidal cyst
│   ├───category L05.0: Pilonidal cyst with abscess
│   └───category L05.9: Pilonidal cyst without abscess
└───category L08: Other local infections of skin and subcutaneous tissue
    ├───category L08.0: Pyoderma
    ├───category L08.1: Erythrasma
    ├───category L08.8: Other specified local infections of skin and subcutaneous tissue
    └───category L08.9: Local infection of skin and subcutaneous tissue, unspecified
```

Similarily, but the other way around, one can print the ancestry of any given entry:

```python
print(icd10_codex.find("C32.1").ancestry())
```

returns

```text
root ICD-10: International Statistical Classification of Diseases and Related Health Problems 10th Revision
└───chapter II: Neoplasms
    └───block C00-C97: Malignant neoplasms
        └───block C00-C75: Malignant neoplasms, stated or presumed to be primary, of specified sites, except of lymphoid, haematopoietic and related tissue
            └───block C30-C39: Malignant neoplasms of respiratory and intrathoracic organs
                └───category C32: Malignant neoplasm of larynx
                    └───category C32.1: Supraglottis
```

***

## Motivation

I recently noticed that there have been some attempts to write a Python package for dealing with [ICD](https://www.who.int/standards/classifications/classification-of-diseases) codes, notably the python package [`icd10-cm`](https://github.com/bryand1/icd10-cm) which is very simple and pythonic, as well as the [`icd-codex`](https://github.com/icd-codex/icd-codex), which was apparently the result of a hackathon and represents the ICD 10 codes as a graph.

Despite those attempts however, there is no package out there that would serve all needs or even just simply deal with the latest 11th revision of ICD. On one hand this might be because the WHO is actually quite stingy with the raw data. If it publishes any data openly at all it is usually some reduced table in a somewhat unconventional format (for programmers and data scientists).

This package attempts to combine the great ideas of the previously mentioned packages but provide a more complete interface to the ICD system.