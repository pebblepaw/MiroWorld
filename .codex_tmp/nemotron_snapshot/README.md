---
license: cc-by-4.0
task_categories:
- text-generation
language:
- en
tags:
- synthetic
- personas
- NVIDIA
- datadesigner
size_categories:
- 1M<n<10M
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
dataset_info:
  features:
  - name: uuid
    dtype: string
  - name: professional_persona
    dtype: string
  - name: sports_persona
    dtype: string
  - name: arts_persona
    dtype: string
  - name: travel_persona
    dtype: string
  - name: culinary_persona
    dtype: string
  - name: persona
    dtype: string
  - name: cultural_background
    dtype: string
  - name: skills_and_expertise
    dtype: string
  - name: skills_and_expertise_list
    dtype: string
  - name: hobbies_and_interests
    dtype: string
  - name: hobbies_and_interests_list
    dtype: string
  - name: career_goals_and_ambitions
    dtype: string
  - name: sex
    dtype: string
  - name: age
    dtype: int64
  - name: marital_status
    dtype: string
  - name: education_level
    dtype: string
  - name: occupation
    dtype: string
  - name: industry
    dtype: string
  - name: planning_area
    dtype: string
  - name: country
    dtype: string
  splits:
  - name: train
    num_bytes: 626406567
    num_examples: 148000
  download_size: 274800528
  dataset_size: 626406567
---

## Nemotron-Personas-Singapore

![Nemotron-Personas-Singapore](images/PGM.png)

*A compound AI approach to personas grounded in real-world distributions*

## Dataset Overview

Nemotron-Personas-Singapore is an open-source (CC BY 4.0) dataset of synthetically-generated personas. This dataset is grounded in real-world demographic, geographic and personality trait distributions in Singapore to capture the diversity and richness of the Singaporean population. It is a variant of [Nemotron-Personas-USA](https://huggingface.co/datasets/nvidia/Nemotron-Personas), and the first Singaporean dataset of its kind aligned with statistics for names, sex, age, ethnicity, religion, marital status and occupation among other attributes. This version of the dataset provides high-quality personas for a variety of modeling use-cases in English.

Nemotron-Personas-Singapore supports Singaporean model builders in developing [Sovereign AI](https://www.nvidia.com/en-us/lp/industries/global-public-sector/sovereign-ai-technical-overview/) systems that incorporate important region-specific demographics and cultural context. The dataset improves diversity of synthetically-generated data, mitigates biases, and prevents [model collapse](https://medium.com/data-science/addressing-concerns-of-model-collapse-from-synthetic-data-in-ai-7cd380208d14) (degradation caused by uncurated training on another model’s outputs) by reflecting Singapore’s real geographic and demographic distributions. In particular, the dataset is designed to be more representative of underlying demographic distributions along multiple axes, including age (e.g. age group), geography (e.g., planning area personas), religion, education, occupation, ethnicity identities, etc., as compared to other persona datasets. As an example, one can produce high-quality, multi-turn chat conversation data with real names, ages, occupation, cultural and education backgrounds, all of which bring unique perspectives and angles to that data.

Produced using [NeMo Data Designer](https://docs.nvidia.com/nemo/microservices/latest/generate-synthetic-data/index.html), an enterprise-grade compound AI system for synthetic data generation, the dataset leverages a proprietary Probabilistic Graphical Model (PGM) along with an Apache-2.0-licensed GPT-OSS-120B model and an ever-expanding set of validators and evaluators built into Data Designer. An extended version of Nemotron-Personas-Singapore will be soon available for use in NeMo Data Designer itself.

This dataset is ready for commercial use.

### What is NOT in the dataset

Given the emphasis on personas, the dataset excludes other fields available in NeMo Data Designer, e.g., first/last names, and synthetic addresses. Also excluded are personas generally of relevance to enterprise clients (e.g., religious, finance, healthcare). Please [reach out](https://www.nvidia.com/en-us/data-center/products/ai-enterprise/contact-sales/) to explore enterprise use-cases.

All data, while mirroring real-world distributions, is completely artificially generated. Any similarity in names or persona-descriptions to actual persons, living or dead, is purely coincidental.

## Data Developer

NVIDIA Corporation 

## Release Date 

Hugging Face 01/27/2026 via [https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore) 

Dataset Creation Date

01/27/2026

## License/Terms of Use

This dataset is licensed under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/deed.en) (CC BY 4.0).

Use Case  
Developers working on Sovereign AI, training LLMs, and/or looking to improve diversity of synthetically generated data, mitigate data/model biases, and prevent model collapse.

Data Version  
1.0 (01/27/2026)

## Intended Use

The Nemotron-Personas-Singapore dataset is intended to be used by the community to continue to improve open models and push the state of the art. The data may be freely used to train any model. We welcome feedback from the open-source community and invite developers, researchers, and data enthusiasts to explore the dataset and build upon it.

The Nemotron-Personas-Singapore dataset is grounded in distributions of self-reported demographic data from the 2024 census of Singapore. As such, its primary goal is to support Sovereign AI development by combating missing data and/or potential biases present in model training data today, especially when it comes to existing persona datasets used in synthetic data generation. Despite the improved data diversity and fidelity to Singapore’s population, we are still limited by data availability, current staleness of data, and reasonable model complexity. This results in some necessary independence assumptions; for instance, that occupations are independent of education degree, given the district, age and sex. 

Note that the dataset is focused on adults only.

## Dataset Details

The dataset contains:

* 888k personas across 148k records   
* 118M tokens, including 48M persona tokens  
* 146k unique names (including preferred English name)  
* 55 planning areas (designated counties for Singapore)


## Seed Data 

In order to capture the socio-demographic and geographic diversity and complexity of Singapore’s population, Nemotron-Personas-Singapore leveraged the following resources:

* 2024 census of Singapore published by the Singapore Department of Statistics  
* English name distribution data obtained from [NLB Name Authorities](https://data.gov.sg/collections/1476/view) and [CEA Salesperson Information](https://data.gov.sg/datasets/d_07c63be0f37e6e59c07a4ddc2fd87fcb/view) from [data.gov.sg](http://data.gov.sg).

## Schema

The dataset includes **20 fields**, comprising **6 persona fields** and **14 contextual fields**, as shown below. The rich set of contextual attributes enables researchers to precisely condition and target specific personas, a capability that is difficult to achieve with existing persona datasets.

| Field | Type | Description |
|-------|------|-------------|
| uuid | string | Globally unique identifier |
| professional_persona | string | Professional persona capturing primary field of work, key professional skills, traits and behavior |
| sports_persona | string | Sports persona describing athletic interests, sport team affiliations, and approach to fitness and exercise |
| arts_persona | string | Arts persona characterizing engagement with creative expression and how the arts shape their identity |
| travel_persona | string | Travel persona capturing travel interests and style |
| culinary_persona | string | Culinary persona describing food/cuisine preferences, cooking skill level, and approach to dining experiences |
| persona | string | A concise general-purpose persona capturing the essence of a person's perspective and approach to life |
| cultural_background | string | Description of the person's cultural background |
| skills_and_expertise | string | Professional and personal skills in narrative format |
| hobbies_and_interests | string | Personal interests and recreational activities in narrative format |
| skills_and_expertise_list | string | List of skills and areas of expertise |
| hobbies_and_interests_list | string | List of hobbies and personal interests |
| career_goals_and_ambitions | string | Professional aspirations and long-term career objectives |
| sex | string | Biological sex (e.g., Male, Female) |
| age | integer | Age in years |
| marital_status | string | Relationship status (e.g., currently married, never married, divorced, widowed) |
| education_level | string | Highest level of education completed |
| occupation | string | Comprehensive professional occupation |
| industry | string | Industry of occupation |
| planning_area | string | Residential Planning Area within Singapore |
| country | string | Country of residence |

## Field & Token Counts

118M tokens (48M persona tokens) across 148k records in English and 20 columns, excluding the globally unique identifier.

![Token Counts](images/token_counts.png)

## Dataset Description & Quality Assessment

The analysis below provides a breakdown across various axes of the dataset to emphasize the built-in diversity and pattern complexity of data. 

### Names Since the focus of this dataset is on personas, names aren’t provided as dedicated fields. However, infused into persona-generation are 8992 unique first names, 4182 unique middle names and 4894 unique last names obtained from [NLB Name Authorities](https://data.gov.sg/collections/1476/view) and [CEA Salesperson Information](https://data.gov.sg/datasets/d_07c63be0f37e6e59c07a4ddc2fd87fcb/view) from [data.gov.sg](http://data.gov.sg). While realistic name distributions are used during persona generation, individual name fields are not exposed in the final dataset to reduce memorization risk and prevent re-identification.

This limitation highlights a broader challenge in constructing name distributions from publicly available administrative and leadership-focused datasets, where representation does not necessarily align with population-wide demographics.

### Age Distribution

Personas are limited to adult Singaporeans (at least 18 years of age). The distribution is relatively balanced across prime working-age groups, with the highest concentrations observed between approximately 25–65 years. 

After age 70, the population size declines progressively, with smaller but still present representations in the elderly and very old age groups.

The dataset focuses on late adolescents and adults (ages 18+), consistent with census reporting granularity. No personas are generated for children under 18.

![Age Distribution](images/age_hist.png)

Male and female counts remain comparable through midlife, while female representation becomes slightly more prominent in older age groups, reflecting higher female longevity. 

![Gender/Age Pyramid](images/gender_pyramid.png)

### Marital Status by Age Group

The heatmap shows age-normalized proportions of marital status in Singapore. Individuals aged 18–24 are predominantly single, with marriage rates increasing rapidly from the late 20s through the 30s and remaining the dominant status until approximately 65–69. The proportion of widowed individuals rises sharply from 60+, becoming dominant in the oldest cohorts. Divorce remains a low-frequency status across all ages, with modest representation beginning in mid-adulthood.

![Marital Status by Age Group](images/marital_by_age_group.png)

### Education Level by Age Group 

Education distributions are conditioned on age cohorts as reported by the Singapore Department of Statistics (Education Attainment of Population Aged 25 and Over, 2024), adapting the 25-29 statistics for those aged 18-24 by limiting the possible outcomes based on age.

![Education Level by Age Group](images/education_by_age.png)

## Geographic Intricacies of Education Attainment

The choropleth maps the **percentage of adult residents with a university degree** by planning area. Graduate shares vary across locations, indicating measurable geographic heterogeneity in tertiary educational attainment within Singapore.

![University Degree Attainment by Planning Area](images/grad_map.png)

## Occupational Categories 

The chart summarizes the distribution of primary job categories among Singapore residents aged 18 and above. Outside of retired individuals and homemakers, employment is heavily concentrated in professional occupations.

![Occupational Categories](images/occupations.png)

Additionally, special care was taken to avoid reinforcing sensitive socio-economic stereotypes associated with ethnicity and religion in Singapore’s multi-cultural context.   

## How to use it

You can load the dataset with the following lines of code.

```python
from datasets import load_dataset

# English personas
nemotron_personas_en = load_dataset("nvidia/Nemotron-Personas-Singapore")
```

## McKAInsey Integration Notes

This repository uses Nemotron-Personas-Singapore as the live persona source for McKAInsey's Stage 2 population sampling flow.

- Local live sampling path:
  - McKAInsey downloads the parquet shards into a local cache and queries them with DuckDB-backed filtering.
- Document-aware relevance:
  - sampled personas are scored against the uploaded policy document's extracted entities, summary, and demographic focus before balanced selection is applied.
- Balanced hybrid selection:
  - final cohort selection preserves representativeness across planning area, income bracket, and age bucket while biasing toward document relevance.
- Demo mode:
  - demo artifacts are generated from a completed real run so the console demo mirrors the same contracts used by live mode.

## Dataset Characterization

### Data Collection Method 

* Hybrid: Human, Synthetic, Automated

### Labeling Method

* Not Applicable

## Dataset Format

* Text

## Dataset Quantification

* Record counts: 148k records (888k persona descriptions)  
* Total data storage: 0.5 GB

## Ethical Considerations 

NVIDIA believes [Trustworthy AI](https://www.nvidia.com/en-us/ai-data-science/trustworthy-ai/) is a shared responsibility and we have established policies and practices to enable development for a wide array of AI applications.  When downloaded or used in accordance with our terms of service, developers should work with their internal teams to ensure this dataset meets requirements for the relevant industry and use case and addresses unforeseen product misuse. 

Please report quality, risk, security vulnerabilities or NVIDIA AI Concerns [here](https://www.nvidia.com/en-us/support/submit-security-vulnerability/).  

## **Citation**

If you find the data useful, please cite:

```bibtex
@software{nvidia/Nemotron-Personas-Singapore,
 author = {Thongpramoon, Pongsasit and March, Verdi and Low, Christopher and Prayaga, Shyamala and Corneil, Dane and Meyer, Yev},
 title = {{Nemotron-Personas-Singapore: Synthetic Personas Aligned to Real-World Distributions for Singapore}},
 month = {January},
 year = {2026},
 url = {https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore}
}

```
