---
marp: true
theme: ie-class
paginate: true
size: 16:9
math: katex
author:
  - name: Daniel Garcia
  - email: dgarciah@faculty.ie.edu
  - url: www.linkedin.com/in/dgarhdez
header: '<img src="../img/ie_logo.png" width="60"><span>Session 14 &mdash; Q&amp;A &amp; Comprehensive Review &middot; <a href="mailto:dgarciah@faculty.ie.edu">dgarciah@faculty.ie.edu</a></span>'
---

<!-- _class: lead -->

# Analytics Engineering: Session 14

## Q&A & Comprehensive Review

---

## Agenda

- Open Q&A on all course topics
- Review of challenging concepts
- Common pitfalls and misconceptions
- Project review and feedback
- Best practices recap

---

## Open Q&A

This session is **student-driven**.

Bring your questions from Sessions 1–13:
- Concepts that were unclear
- Errors you encountered in your project
- Topics you want to explore deeper
- Certification-specific concerns

---

## Review: The dbt Workflow

The full lifecycle in one view:

![center w:1100](../img/diagrams/layers.svg)

Key commands at each stage:
- `dbt source freshness` → Sources
- `dbt seed` → Static data
- `dbt build` → Models + Tests + Seeds + Snapshots (in DAG order)
- `dbt docs generate` → Documentation

---

## Common Pitfalls: Modeling

| Pitfall | Solution |
| :--- | :--- |
| Joining sources directly in marts | Always go through staging first |
| Business logic in staging models | Staging = clean only, logic in intermediate |
| Aggregations causing fan-out | Pre-aggregate in intermediate (like `int_order_items_summary`) |
| Circular references | Redesign the DAG — data flows one way |

---

## Common Pitfalls: Testing

| Pitfall | Solution |
| :--- | :--- |
| Only testing marts | Test all layers — staging PKs, intermediate joins, mart business rules |
| Forgetting `relationships` tests | Validate foreign keys between layers |
| Not using `dbt build` | `dbt build` runs tests immediately after models — catches issues early |
| Ignoring test failures | Fix failures before merging to main |

---

## Common Pitfalls: Configuration

| Pitfall | Solution |
| :--- | :--- |
| Wrong materialization | Views for staging, tables for marts, incremental for large facts |
| Missing `unique_key` on incremental | Always set `unique_key` to prevent duplicates |
| Contracts without all columns typed | Every column needs `data_type` when contract is enforced |
| Snapshot without `updated_at` | Timestamp strategy requires the column to exist and be populated |

---

## Review: Certification Domains

The 8 domains tested on the exam:

| # | Domain | Key Topics |
| :--- | :--- | :--- |
| 1 | Developing dbt models | ref, source, materializations, DAGs, Python models, grants |
| 2 | Model governance | Contracts, versions, access, deprecation |
| 3 | Debugging errors | Compiled SQL, dbt.log, YAML vs SQL errors |
| 4 | Managing pipelines | DAG failures, dbt clone, integrated tools |
| 5 | Implementing tests | Generic, singular, custom generic |
| 6 | Documentation | YAML descriptions, doc blocks, docs site |
| 7 | External dependencies | Exposures, source freshness |
| 8 | Leveraging state | state:modified, dbt retry, result selectors |

---

## Tricky Exam Topics

Topics that students commonly find challenging:

- **Incremental strategies**: When to use append vs merge vs delete+insert
- **Snapshot config**: timestamp vs check strategy, what columns dbt adds
- **State selectors**: `state:modified` vs `state:new` vs `result:error`
- **Contract enforcement**: What happens when a contract fails at build time
- **Custom generic tests**: How they differ from singular tests
- **Exposures**: How they appear in the DAG and what `depends_on` does
- **`dbt build` vs `dbt run`**: Build includes tests, seeds, and snapshots

---

## Project Review

Let's review your projects together:

- [ ] All staging models with sources defined
- [ ] Intermediate models isolating complexity
- [ ] Mart models (dimensions and facts)
- [ ] Tests at every layer (generic, singular, custom generic)
- [ ] Documentation on all public models
- [ ] At least one exposure defined
- [ ] At least one incremental model
- [ ] At least one snapshot
- [ ] Contracts on mart models
- [ ] `dbt build` passes with zero failures

---

## Best Practices Recap

- [ ] **Naming**: Consistent `stg_`, `int_`, `dim_`, `mart_` prefixes
- [ ] **Structure**: Sources → Staging → Intermediate → Marts
- [ ] **Testing**: Test all primary keys and foreign keys
- [ ] **Documentation**: Descriptions for all public models and columns
- [ ] **Git**: Atomic commits, descriptive PRs, branch per feature
- [ ] **Materializations**: Views for staging, tables for marts
- [ ] **DRY**: One definition of each metric, referenced via `ref()`

---

## What have we learned in this session

- Addressed open questions across all course topics
- Reviewed common pitfalls in modeling, testing, and configuration
- Reviewed all 8 certification domains and tricky exam topics
- Received feedback on projects
- Recapped best practices for production-ready dbt projects

**Next Session:** Certification Prep & Mock Exam.
