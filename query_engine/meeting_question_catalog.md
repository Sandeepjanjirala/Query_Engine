# Executive AGM/RI Review Meeting Question Catalog

This catalog documents the natural-language questions supported by the **Query Engine** for executive review meetings (AGM, RI, Zone, and Branch).

---

## 🏛️ Architectural Framework & Data Rules

The query engine operates on a clean separation of concerns across all questions:

```text
Selected AGM/RI/Zone/Branch = Scope (filters.py)
"by Branch/RI/Zone/AGM"     = Grouping Dimension (params.py)
Metric                     = What is measured (metric_registry.py)
Ranking                    = How it is ordered (analytics.py)
CY/LY                      = Time Comparison (analytics.py)
Threshold                  = Exception Condition (analytics.py)
```

### Standard Output Format
All table results adhere to the standardized executive column format:
`| Rank | Branch / Entity | Current Year | Last Year | Change |`

- **Percentage Metrics** (e.g. Dropout %): Change is formatted in percentage points (`pp`, e.g. `+0.97 pp`, `-0.32 pp`).
- **Count Metrics** (e.g. Dropout Count, Net Strength): Change is formatted as numeric integer count difference (e.g. `+12`, `-5`).

---

## 📋 Catalog of Supported Meeting Questions by Category

### 1. Executive Summary & Overall Performance
*Purpose: First questions asked by an AGM or RI when starting a review meeting.*

- `Give me the complete summary.`
- `Give me the overall performance.`
- `Give me the overall summary.`
- `Give me a performance overview.`
- `Give me the current status.`
- `Give me the complete performance report.`
- `How are we performing overall?`
- `What is the overall position?`
- `Give me the key metrics.`
- `Give me the important metrics.`
- `Give me my complete summary.`
- `How am I performing?`
- `Give me complete summary of Mr.M.Ramana.`
- `Give me complete summary of Mr.Ahmedali.`
- `Give me complete summary of Mr.M.V.Suresh.`
- `Give me complete summary of Kakinada zone.`
- `Give me complete summary of KAKINADA 1.`

---

### 2. Dropout Analysis (DP & DPP) — Basic & YoY
*Purpose: Evaluate dropout rates, counts, and year-over-year progress.*

#### Basic Lookup & Scope Totals:
- `What is the dropout percentage?`
- `What is the dropout count?`
- `How many students dropped out?`
- `What is our dropout rate?`
- `How many dropouts do we have?`

#### Current Year vs Previous Year (YoY):
- `What is the dropout percentage compared with last year?`
- `How has dropout changed from last year?`
- `Did dropout improve this year?`
- `Did dropout increase compared with last year?`
- `How much did dropout change?`
- `Show CY vs LY dropout.`
- `Show current and previous year dropout.`

#### Increase / Decrease & Improvement / Decline:
- `Which branches increased their dropouts?`
- `Which branches reduced their dropouts?`
- `Which branches had the biggest increase?`
- `Which branches had the biggest reduction?`
- `Which branches are getting worse?`
- `Which branches are improving?`

---

### 3. "Where is the problem?" Drill-Down Analysis
*Purpose: Hierarchical drill-down from AGM → RI → Zone → Branch to identify problem areas.*

- `Which RI has the highest dropout?`
- `Which RI has the lowest dropout?`
- `Which RI has the highest dropout percentage?`
- `Which RI has the biggest increase in dropout?`
- `Which RI improved the most?`
- `Which RI declined the most?`
- `Which RI needs attention?`
- `Which branches under the worst RI have the highest dropout?`
- `Which branches are responsible for the increase?`
- `Which branches have dropout above 15%?`
- `Which branches have dropout above 20%?`

---

### 4. RI Review Meeting Questions
*Purpose: Questions asked by an RI (e.g. Mr. M. Ramana) managing their assigned branches.*

#### RI Overall Performance:
- `Give me my complete summary.`
- `How am I performing?`
- `Give me my performance report.`
- `What is my dropout percentage?`
- `How many students dropped out?`
- `What is my current strength?`
- `How many staff do I have?`
- `What is my student teacher ratio?`

#### RI Branch Breakdown:
- `Show my branches.`
- `How many branches are under me?`
- `Show dropout by branch.`
- `Show dropout percentage by branch.`
- `Show current strength by branch.`
- `Show staff count by branch.`

#### RI Problem Branch Identification:
- `RI M Ramana top branches with highest dropout percentage`
- `RI M ramana top branches with dropouts count`
- `Which branches have the highest dropout?`
- `Top 5 branches with highest dropout.`
- `Top 5 branches by dropout percentage.`
- `Which branches under Mr.M.Ramana have dropout above 15%?`
- `Which branches under Mr.M.Ramana have dropout above 20%?`
- `Which branches under Mr.M.Ramana are performing poorly?`
- `Which branch under Mr.M.Ramana needs immediate attention?`

---

### 5. Net Strength & Grant Strength Analysis (NS, NSD, GS, SD)
*Purpose: Monitor student enrollment trends, gains, and losses.*

- `What is the current strength?`
- `What was the strength last year?`
- `How much has strength changed?`
- `Which branches gained strength?`
- `Which branches lost strength?`
- `Which branch has the highest strength?`
- `Which branch has the lowest strength?`
- `Which branches lost the most students?`
- `Which branches gained the most students?`
- `Which RI has the highest strength?`
- `Which RI lost the most strength?`
- `Which RI gained the most strength?`
- `Which branches lost strength but also have high dropout?`
- `Which branches have declining strength?`

---

### 6. Student-Teacher Ratio (STR) & Staff Analysis (SC, AC, AD)
*Purpose: Optimize staffing levels, identify imbalances, and evaluate administrative staffing.*

#### Student-Teacher Ratio (STR):
- `What is the student teacher ratio?`
- `Which branches have the highest STR?`
- `Which branches have the lowest STR?`
- `Which RI has the highest STR?`
- `Which branches have an unusually high STR?`
- `Which branches have low student strength but high staff?`
- `Which branches have high student strength but low staff?`

#### Staff Count & Categories:
- `What is the total staff count?`
- `Which branch has the highest staff count?`
- `Which branch has the lowest staff count?`
- `Which RI has the highest staff strength?`
- `How has staff count changed from last year?`
- `Which branches added staff?`
- `Which branches reduced staff?`
- `What is the administration staff count?`
- `What is the activity staff count?`

---

### 7. Resource Efficiency & Cross-Metric Analysis
*Purpose: Combine multiple metrics (Dropout + Strength + Staff + STR) for decision-support analysis.*

- `Which branches have high dropout but low staff?`
- `Which branches have high dropout and high strength?`
- `Which branches have low strength but high staff?`
- `Which branches have high student teacher ratio and high dropout?`
- `Which branches have declining strength and increasing dropout?`

---

### 8. Academic Education Category YoY (PP, PS, HS)
*Purpose: Analyze performance across Pre-Primary (PP), Primary School (PS), and High School (HS).*

- `Which category has the highest dropout?`
- `Which category has the lowest dropout?`
- `Which category has the highest dropout percentage?`
- `Which category improved most?`
- `Which category declined most?`
- `Show PP, PS and HS dropout percentage.`
- `Show CY vs LY for PP, PS and HS.`
- `Which category increased the most?`
- `Which category reduced dropout the most?`
- `Which category has the highest strength?`
- `Which category lost the most strength?`
- `Which category gained the most strength?`
- `Which category has the highest staff requirement?`
- `What is the student strength per section for each category?`

---

### 9. Section & Classroom Utilization (NOS, SPS, NOCR, NOOR, NOVR, ARCS)
*Purpose: Evaluate class sizing and capacity management.*

#### Sections & Students per Section (SPS):
- `How many sections do we have?`
- `Which branches have the most sections?`
- `Which branches have the fewest sections?`
- `What is the average student strength per section?`
- `Which branches have low students per section?`
- `Which branches have high students per section?`

#### Classrooms & Capacity:
- `How many classrooms do we have?`
- `Which branches have the most classrooms?`
- `Which branches have empty classrooms?`
- `Which branches have the highest room vacancy?`
- `Which branches have the highest occupancy?`
- `Which branches have underutilized rooms?`

---

### 10. Room Utilization & Vacancy Analysis
*Purpose: Identify physical infrastructure inefficiencies and vacant capacity.*

- `Which branches have vacant classrooms?`
- `Which branches have the highest room vacancy?`
- `Which branches have more rooms than required?`
- `Which branches have maximum room utilization?`
- `Which branches have low occupancy?`
- `Which branches have high student strength but vacant rooms?`
- `Which branches have low strength and many classrooms?`
- `Which branches have high occupancy and high dropout?`

---

### 11. Top N & Bottom N Branch Rankings (Global & Scoped)
*Purpose: Rank branches globally or within a selected AGM, RI, or Zone scope.*

#### Global Rankings:
- `Top 5 branches by dropout.`
- `Top 10 branches by dropout.`
- `Top 5 branches by dropout percentage.`
- `Top 5 branches by strength.`
- `Top 5 branches by staff count.`
- `Top 5 branches by STR.`
- `Top 5 branches by sections.`
- `Top 5 branches by room vacancy.`
- `Bottom 5 branches by dropout.`
- `Bottom 5 branches by strength.`
- `Bottom 5 branches by staff count.`
- `Bottom 5 branches by STR.`

#### Scoped Rankings:
- `Top 5 branches under Mr.Ahmedali by dropout.`
- `Top 5 branches under Mr.M.Ramana by dropout percentage.`
- `Top 5 branches in Kakinada zone by strength.`
- `Top 5 branches under Mr.M.V.Suresh by STR.`

---

### 12. Threshold & Exception Filtering
*Purpose: Filter branches or groups exceeding operational threshold limits.*

- `Which branches have dropout percentage above 15%?`
- `Which branches have dropout percentage above 20%?`
- `Which branches have dropout below 5%?`
- `Which branches have strength below 500?`
- `Which branches have strength above 1,000?`
- `Which branches have staff count above 50?`
- `Which branches have STR above 20?`
- `Which branches have more than 10 vacant rooms?`
- `Which branches under Mr.M.Ramana have dropout above 15%?`
- `Which branches under Mr.Ahmedali have strength below 500?`
- `Which branches in Kakinada zone have more than 10 empty rooms?`

---

### 13. Year-over-Year (YoY) Change & Most Improved / Worst Decline
*Purpose: Measure YoY progress, identify top turnarounds, and flag deteriorating entities.*

#### General Change:
- `What changed compared with last year?`
- `Which branches improved?`
- `Which branches declined?`
- `Which branches increased dropout?`
- `Which branches reduced dropout?`
- `Which branches gained strength?`
- `Which branches lost strength?`

#### Most Improved:
- `Which branches improved the most?`
- `Which RI improved the most?`
- `Which AGM improved the most?`
- `Which zone improved the most?`

#### Worst Decline:
- `Which branches declined the most?`
- `Which RI declined the most?`
- `Which AGM declined the most?`
- `Which zone declined the most?`

---

### 14. Admission Type Analysis (Existing vs New — E vs N)
*Purpose: Compare retention and dropout rates between existing and newly admitted students.*

- `Which has higher dropout, existing or new students?`
- `Compare existing and new dropout.`
- `Compare E vs N dropout percentage.`
- `Which admission type has higher strength?`
- `Which admission type improved?`
- `Which admission type declined?`
- `Compare PP existing vs new.`
- `Compare PS existing vs new.`
- `Compare HS existing vs new.`

---

### 15. Executive Diagnostic & Attention Queries
*Purpose: Flag top operational priorities requiring immediate executive action.*

- `What needs my attention?`
- `Which branches need attention?`
- `Where are the major problems?`
- `Show me the problem branches.`
- `What are the biggest concerns?`
- `Where should I focus?`
- `Which branches are performing poorly?`

---

## 🛠️ Adding New Meeting Questions

When adding support for a new executive question:
1. **Identify the Metric**: Register or map the canonical metric token in `metric_registry.py` (e.g. `DPP`, `DP`, `NS`, `STR`).
2. **Define the Operation**: Add intent routing patterns in `router.py` (e.g. `ranking`, `group_by`, `threshold`, `comparison`, `entity_summary`).
3. **Keep Scope Independent**: Never hardcode entity filters into grouping logic — rely on `apply_filter_context()` in `filters.py`.
4. **Append to this Catalog**: Document the new question under the appropriate category in `MEETING_QUESTION_CATALOG.md`.
