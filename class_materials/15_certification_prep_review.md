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
header: '<img src="../img/ie_logo.png" width="60"><span>Session 15 &mdash; Certification Prep &amp; Mock Exam &middot; <a href="mailto:dgarciah@faculty.ie.edu">dgarciah@faculty.ie.edu</a></span>'
---

<!-- _class: lead -->

# Analytics Engineering: Session 15

## Certification Prep & Mock Exam

---

## Agenda

- Certification Exam Overview
- Domain-by-Domain Quick Review
- Mock Exam (Timed)
- Group Answer Review
- Targeted Weak-Area Review
- Next Steps

---

## Certification Exam Overview

- **Format**: 65 Multiple Choice Questions.
- **Time**: 2 Hours.
- **Passing**: 65% (43 correct answers).
- **Focus**: Practical application, not just theory.
- **Version**: dbt 1.7+

**Strategy**:
- Read each question carefully — look for keywords like "always", "never", "best".
- Flag and skip difficult questions — come back to them.
- Manage your time — ~1.8 minutes per question.

---

## Domain 1: Developing dbt Models

**Key topics**:
- `ref()` and `source()` functions
- Core materializations (view, table, ephemeral, incremental)
- Modularity, DRY, CTEs
- DAG structure and execution order
- `dbt_project.yml` configuration
- dbt commands: `run`, `test`, `build`, `seed`, `docs`
- Python models
- `grants` configuration

**Sample question**: *"What happens if Model A uses `ref('Model B')` and Model B uses `ref('Model A')`?"*

→ dbt raises a circular dependency error during parsing.

---

## Domain 2: Model Governance

**Key topics**:
- Contracts: enforcing schema at build time
- Versions: managing breaking changes
- Deprecation: signaling end-of-life
- Access levels: public, protected, private

**Sample question**: *"If a model has `contract: {enforced: true}` and a column returns `varchar` instead of `int`, what happens?"*

→ The build fails with a contract violation error.

---

## Domain 3: Debugging Errors

**Key topics**:
- Reading logged error messages (bottom up)
- Troubleshooting with compiled SQL (`target/compiled/`)
- YAML compilation errors (indentation, syntax)
- Distinguishing dbt errors from database errors
- Developing and testing fixes before merging

**Sample question**: *"A model fails with 'relation does not exist'. Where should you look first?"*

→ Check the `ref()` or `source()` name for typos, then check compiled SQL.

---

## Domain 4: Managing Data Pipelines

**Key topics**:
- Managing DAG failure points
- `dbt clone` for environment management
- Troubleshooting errors from integrated tools

**Sample question**: *"After a partial pipeline failure, what is the most efficient way to resume?"*

→ Use `dbt retry` to re-run only the failed nodes and their downstream.

---

## Domain 5: Implementing dbt Tests

**Key topics**:
- Generic tests: `unique`, `not_null`, `accepted_values`, `relationships`
- Singular tests: custom SQL in `tests/`
- Custom generic tests: reusable macros in `macros/`
- Testing sources and models
- `dbt build` runs tests in DAG order

**Sample question**: *"What is the difference between a singular test and a custom generic test?"*

→ Singular tests are one-off SQL files. Custom generic tests are reusable Jinja macros that can be applied to any model via YAML.

---

## Domain 6: Documentation

**Key topics**:
- Adding descriptions in YAML files
- Doc blocks with `{% docs %}` in markdown
- `dbt docs generate` and `dbt docs serve`
- Source, model, and column documentation

**Sample question**: *"How do you reference a doc block in a model's YAML description?"*

→ `description: '{{ doc("my_doc_block_name") }}'`

---

## Domain 7: External Dependencies

**Key topics**:
- Exposures: defining downstream consumers (dashboards, reports)
- Source freshness: `loaded_at_field`, `warn_after`, `error_after`

**Sample question**: *"What is the purpose of defining an exposure in dbt?"*

→ Exposures document downstream consumers (dashboards, ML models) and make them visible in the lineage graph for impact analysis.

---

## Domain 8: Leveraging dbt State

**Key topics**:
- State artifacts: `manifest.json`
- `state:modified` and `state:new` selectors
- `dbt retry` for re-running failed nodes
- Result selectors: `result:error`, `result:fail`, `result:pass`

**Sample question**: *"What is the difference between `state:modified` and `result:error`?"*

→ `state:modified` compares current code to a previous manifest. `result:error` looks at the results of the last run to find nodes that errored.

---

## Mock Exam

**Instructions**:
- 30 questions, 50 minutes (simulating exam pace)
- Work individually — no notes or docs
- Mark questions you're unsure about
- We'll review answers together afterward

*Starting now...*

---

## Mock Exam Review

Let's go through the answers together.

For each question:
1. What is the correct answer?
2. Why are the other options wrong?
3. What concept does this test?

*Focus on understanding the "why", not just memorizing answers.*

---

## Targeted Review

Based on the mock exam results, let's focus on the areas where the group scored lowest.

Common weak areas:
- Incremental strategies and `is_incremental()` logic
- Snapshot configuration details (dbt-added columns)
- State vs result selectors
- Contract constraint types
- `dbt build` vs `dbt run` vs `dbt test`

---

## Exam Day Tips

1. **Read carefully**: Watch for "BEST", "ALWAYS", "NEVER" in questions.
2. **Eliminate**: Remove obviously wrong answers first.
3. **Time management**: Don't spend more than 2 minutes on any question.
4. **Flag and return**: Mark uncertain questions and come back.
5. **Compiled SQL**: Many questions test whether you understand what dbt sends to the database.
6. **Think in DAGs**: Model execution order, downstream impact, selectors.

---

## Next Steps

1. **Take the exam**: [getdbt.com/certifications](https://www.getdbt.com/certifications/analytics-engineer-certification-exam)
2. **Study resources**:
   - [dbt Fundamentals course](https://learn.getdbt.com/courses/dbt-fundamentals)
   - [Official Study Guide (PDF)](https://www.getdbt.com/dbt-assets/certifications/dbt-certificate-study-guide)
   - [dbt Documentation](https://docs.getdbt.com)
3. **Practice**: Build your own dbt project with a different dataset.
4. **Community**: Join the [dbt Slack](https://www.getdbt.com/community/join-the-community) for support.

---

## Good Luck!

You are now ready to be a **dbt Certified Analytics Engineer**.

---

## What have we learned in this session

- Reviewed all 8 certification domains with sample questions
- Completed a timed mock exam
- Identified and reviewed weak areas
- Exam strategy and time management tips

**End of Course.**
