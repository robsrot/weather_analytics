---
marp: true
theme: ie-class
paginate: true
size: 16:9
author:
  - name: Daniel Garcia
  - email: dgarciah@faculty.ie.edu
  - url: www.linkedin.com/in/dgarhdez
header: '<img src="../img/ie_logo.png" width="60"><span>Session 1 &mdash; Intro &amp; Course Overview &middot; <a href="mailto:dgarciah@faculty.ie.edu">dgarciah@faculty.ie.edu</a></span>'
---

<!-- _class: lead -->

# Analytics Engineering: Session 1

## Introduction to Analytics Engineering & Course Overview

---

## Agenda

- Course logistics & the project you will build
- What is Analytics Engineering?
- The Analytics Development Lifecycle (ADLC)
- ELT vs ETL
- Data Team Roles & the Modern Data Stack
- What is dbt?
- The dbt ecosystem
- Certification overview

---

## Course Logistics

**15 sessions**, structured around the **8 domains** of the dbt Analytics Engineering Certification.

- **Concept sessions**: theory + live coding on the course repo.
- **Hands-on workshops**: Sessions **5, 8, and 12** — you build, I coach.
- **Certification prep**: Sessions 14 (Q&A) and 15 (exam strategy).

**Tools we will use**:

- **dbt Core** (local, open-source), **DuckDB** as the warehouse.
- **VS Code** + the **dbt Power User** extension.
- **Git & GitHub** for version control and collaboration.
- **Python** for the environment manager (`uv`) and Python models.

---

## The Course Project

You will build a **complete, production-style dbt project** on an ecommerce dataset.

- **Dataset**: 14 raw tables (orders, customers, products, shipments…) loaded from Parquet into DuckDB.
- **Three-layer architecture**: `staging → intermediate → marts`.
- **Production features** (added progressively): tests, documentation, packages, macros, incremental models, snapshots, contracts, CI/CD patterns.
- **Workflow**: fork the course repo, then work entirely inside **your fork** — feature branches, Pull Requests into your fork's `main`, no pushes to the instructor's repo.

*By the end of the course you will have a portfolio-ready dbt project and be ready for the certification exam.*

---

## What is Analytics Engineering?

A discipline that applies **software engineering principles** to data transformation.

- **The Practices**: Version control (Git), CI/CD, Automated Testing, Modular Code.
- **The Gap**: Bridges the gap between Data Engineering (Infrastructure/Ingestion) and Data Analysis (Insights/Reporting).
- **The Outcome**: Trusted, documented, and reliable datasets that the business can depend on.

---

## The Analytics Development Lifecycle (ADLC)

The ADLC is the workflow that analytics engineers follow to deliver trustworthy data.

1. **Build**: Write modular, tested transformations.
2. **Collaborate**: Version control, code review, and documentation.
3. **Deploy**: Push to production with CI/CD.
4. **Monitor**: Track data freshness, test results, and pipeline health.

*dbt is designed around the ADLC — it provides tools for every stage.*

---

## ELT vs ETL

The modern data stack flips the traditional approach.

| | **ETL** (Traditional) | **ELT** (Modern) |
| :--- | :--- | :--- |
| **Transform** | Before loading (in a staging area) | After loading (in the warehouse) |
| **Tools** | Informatica, SSIS | dbt, SQL |
| **Scalability** | Limited by staging compute | Leverages warehouse compute |
| **Flexibility** | Rigid, schema-first | Agile, iterate quickly |

**dbt is the "T" in ELT** — it transforms data already in your warehouse.

---

## Data Team Roles

![center width:1100px](../img/roles.png)

---

## Where the Analytics Engineer Fits

- **Data Engineer**: Builds pipelines (Extract & Load). Focuses on infrastructure.
- **Analytics Engineer**: Transforms data (the "T"). Focuses on modeling, testing, docs.
- **Data Analyst**: Consumes data. Focuses on insights and reporting.

The Analytics Engineer sits between Engineering and Analysis, ensuring data is **reliable, documented, and queryable**.

---

## The Modern Data Stack

![center width:1200px](../img/data_stack.png)

A layered ecosystem: **ingest → store → transform → serve**. dbt owns the *transform* layer.

---

## What is dbt?

**dbt** is the transformation workflow that lets you quickly and collaboratively deploy analytics code.

- **The "T" in ELT**: dbt doesn't extract or load data. It transforms data already in your warehouse.
- **Compiler**: Compiles Jinja (templating) and SQL into raw SQL.
- **Runner**: Executes that SQL against your database (DuckDB, Snowflake, etc.).
- **The Data Control Plane**: Manages testing, documentation, and lineage in one place.

---

## The dbt Ecosystem

dbt is the **de-facto standard** for transformation in the Modern Data Stack.

- **Community**: Thousands of professionals in the [dbt Slack](https://www.getdbt.com/community/join-the-community) — channels for DuckDB, testing, dbt Cloud, job postings, and more.
- **Packages (dbt Hub)**: `dbt_utils`, `dbt_expectations`, `codegen`, `dbt_project_evaluator` — reusable macros and tests maintained by the community.
- **Warehouses**: Official adapters for Snowflake, BigQuery, Redshift, Databricks, Postgres, **DuckDB**, and more.
- **Integrations**: Fivetran & Airbyte (ingestion), Airflow/Dagster/Prefect (orchestration), Looker/Tableau/Metabase (BI).
- **Career**: "Analytics Engineer" is one of the fastest-growing roles in data.

---

## Certification Overview

This course prepares you for the **dbt Analytics Engineering Certification**.

- **Format**: 65 Multiple Choice Questions, 2 Hours, 65% to pass.
- **8 Domains**:
  1. Developing dbt models
  2. Understanding dbt model governance
  3. Debugging data modeling errors
  4. Managing data pipelines
  5. Implementing dbt tests
  6. Creating and maintaining documentation
  7. Implementing external dependencies
  8. Leveraging dbt state

---

## What have we learned in this session

- What Analytics Engineering is and the ADLC
- ELT vs ETL and where dbt fits
- The roles in a modern data team and where the AE sits
- What dbt is (compiler, runner, control plane) and its ecosystem
- The structure of the certification exam and its 8 domains
- How the course is structured and what we will build

**Next session:** Setting Up dbt & Building First Models.
