# MRRT Questionnaire - Processed CSV Format Comparison

## Overview
This document compares two approaches for structuring the extracted questionnaire data.

## Files Created
1. `sample_processed_wide_format.csv` - Wide format (one row per response)
2. `sample_processed_long_format.csv` - Long/normalized format (multiple rows per response)

---

## Format 1: Wide Format

### Structure
- **One row per questionnaire response**
- **One column per question field**
- Very wide table (100+ columns)

### Sample
```
response_id | interviewer | country | institution | num_linacs | clinical_site_brain_treating | pct_brain_external_beam | ...
R001        | Dr. Chen    | Germany | UH Munich   | 4          | Yes                          | 85                      | ...
R002        | J Martinez  | USA     | Memorial CC | 3          | Yes                          | 70                      | ...
```

### Pros ✅
- **Familiar format** - looks like a traditional spreadsheet
- **Easy to view** one response at a time in Excel/Google Sheets
- **Simple exports** to PowerPoint/reports (one row = one interview)
- **Quick filtering** by institution/country

### Cons ❌
- **Very wide** - 100+ columns, difficult to scroll
- **Hard to analyze** multi-select questions (e.g., "treating brain, prostate, liver")
- **Difficult queries** - "Show all pain points across all respondents" requires multiple columns
- **Sparse data** - many empty cells where questions don't apply
- **Inflexible** - hard to add new questions or change structure

### Best For
- Executive summaries
- Viewing individual responses
- Basic Excel analysis
- Simple demographics tables

---

## Format 2: Long/Normalized Format (RECOMMENDED)

### Structure
- **Multiple rows per questionnaire response**
- **One row per question answer**
- Includes metadata about each question

### Sample
```
response_id | section        | question_id | question_text                    | response_value | response_text
R001        | background     | Q005        | Number of LINACs                 | 4              |
R001        | clinical_sites | Q032        | Brain - % Planned External Beam  | 85             |
R001        | pain_points    | Q065        | Brain/Head-Neck Coil Main Pains  |                | Head coil positioning is challenging...
R002        | background     | Q005        | Number of LINACs                 | 3              |
R002        | clinical_sites | Q032        | Brain - % Planned External Beam  | 70             |
```

### Pros ✅
- **Powerful analysis** - easy to aggregate across all responses
- **Flexible querying** - "Show all pain points" = filter by section='pain_points'
- **Handles complexity** - multi-select, conditional questions work naturally
- **Efficient storage** - no empty cells
- **Easy to extend** - add new questions without changing structure
- **Perfect for AI/ML** - structured format for text analysis
- **Database-ready** - can import directly into SQL/analytics tools

### Cons ❌
- **Less intuitive** for non-technical users
- **Requires tools** - need SQL, Python, or BI tools to analyze effectively
- **Can't view** full response in one row

### Best For
- **Systematic analysis** (RECOMMENDED for your thesis)
- Text mining and sentiment analysis
- Identifying common pain points
- Cross-tabulation (e.g., "pain points by institution size")
- Statistical analysis
- Database storage
- AI/LLM processing

---

## Recommendations

### For Your Boss's Review
**Show both formats**, but recommend **Long Format** for these reasons:

1. **Better for your thesis research questions:**
   - "What are common pain points?" → Easy query: filter section='pain_points'
   - "How does MR usage vary by institution size?" → Join background + usage data
   - "Which vendors are most mentioned?" → Search across all vendor fields

2. **Scalable:**
   - If you get 100 questionnaires, analysis remains simple
   - New questions don't require restructuring

3. **AI-friendly:**
   - Can feed pain points directly to LLMs for theme extraction
   - Easy to build dashboards in Tableau/PowerBI

### Hybrid Approach
You can maintain **both**:
- **Long format** as master database (source of truth)
- **Generate wide format** views on-demand for specific reports
- Use Python/SQL to pivot between formats as needed

---

## Next Steps

1. **Review both samples** with your boss
2. **Decide on format** (or use both)
3. **Confirm interesting questions** to prioritize in extraction
4. **Choose extraction method:**
   - Option A: Document AI service (Azure/Google/AWS)
   - Option B: Python OCR pipeline (opencv + tesseract)

## Technical Note
The long format follows **Tidy Data** principles (Hadley Wickham):
- Each variable forms a column
- Each observation forms a row
- Each type of observational unit forms a table

This makes it ideal for modern data analysis workflows (R, Python, SQL).
