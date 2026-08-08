# Data Pack — READ THIS FIRST

These files are REAL extracted assets from two live Google Ads accounts that used the target playbook.
They are INPUTS. Do not regenerate, invent, or "improve" their contents in code.
Load them at runtime; treat them as read-only bundled data.

| File | What it is | How to use it |
|---|---|---|
| `negatives_universal.csv` | 649 real phrase-match negative keywords (Layer 1 master list, mined across the agency's clients) | Bundle as-is. Every generated account gets all of these in its shared negative list. Never generate substitutes. |
| `editor_schema_headers.txt` | The exact 312-column, TAB-separated header row from a real Google Ads Editor export | The export module MUST write this exact header row, then fill only the columns it needs and leave the rest blank. Do not hardcode a shortened header list. |
| `settings_block_reference.json` | The real campaign settings from the top-performing campaign | Use these as the default settings applied to every generated campaign. |
| `rsa_skeleton.json` | Real RSA headline/description structure, annotated with ROLES, plus char limits and asset patterns | Feed the roles + examples to the AI as the template to fill per service/city. Keep `literal: true` slots verbatim. |
| `generation_rules.md` | tCPA, budget, keyword formula, naming, negative match-type rules | Implement as deterministic code, not AI judgment. |

## Encoding warning
The Editor file is **UTF-16, tab-separated**. Exports that use UTF-8 or commas will fail or garble on import. Match the encoding of `editor_schema_headers.txt`'s source exactly and test an import before building further.
