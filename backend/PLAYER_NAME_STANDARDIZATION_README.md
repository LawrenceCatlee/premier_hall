# Player Name Standardization Architecture

## Overview

This document describes the new player name standardization system that improves matching accuracy between different data sources (Transfermarkt, Wikipedia, Pulselive).

## Architecture Components

### 1. `player_name_mapper.py`
**Purpose**: Direct name mapping using dictionary approach
- Contains `NAME_MAPPING` dictionary: "non_standard_name": "standard_name"
- Provides `standardize_player_name()` function for direct mapping
- Includes analysis tools to identify name mismatches

**Key Features**:
- Direct mapping is more reliable than complex normalization
- Easy to maintain and extend
- Includes analysis functions to discover new mappings

### 2. `player_name_normalizer.py`
**Purpose**: Traditional name normalization functions
- Handles accent removal, nickname expansion, etc.
- Used as fallback when direct mapping doesn't exist
- Provides similarity scoring functions

### 3. `pulselive_data.py`
**Purpose**: Centralized Pulselive API data access
- Fetches and caches Premier League player data
- Provides player_id lookup functionality
- Used by both scraping modules

### 4. Updated Modules

#### `premier_league_awards.py`
- Now uses `player_name_mapper` before traditional normalization
- Imports from `pulselive_data` instead of direct API calls
- Improved matching accuracy for known name variations

#### `player_premier_team_200.py`
- Added player_id matching and inclusion in output
- Uses new name mapping system
- Outputs player_id as first column for easier merging

## Name Mapping Process

### Step 1: Direct Mapping
```python
from player_name_mapper import standardize_player_name

# Direct mapping examples
"Alisson" -> "alisson becker"
"Heung-min Son" -> "son heung-min"
"Andy Cole" -> "andrew cole"
"Petr Čech" -> "petr cech"
```

### Step 2: Traditional Normalization (Fallback)
If no direct mapping exists, falls back to traditional normalization:
- Accent removal (Čech -> Cech)
- Nickname expansion (Andy -> Andrew)
- Character standardization (ß -> ss)

### Step 3: Fuzzy Matching
Final fallback using similarity scoring for edge cases.

## Current Name Mappings

The system currently handles these name variations:

### Transfermarkt to Premier League
- "alisson" → "alisson becker"
- "heung-min son" → "son heung-min" 
- "yakubu aiyegbeni" → "yakubu"

### Special Character Normalization
- "andy cole" → "andrew cole"
- "ruud van nistelrooy" → "ruud van nistelrooij"
- "petr čech" → "petr cech"
- "wojciech szczęsny" → "wojciech szczesny"
- "nemanja vidić" → "nemanja vidic"
- "ole gunnar solskjær" → "ole gunnar solskjaer"
- "ilkay gündoğan" → "ilkay gundogan"
- "branislav ivanović" → "branislav ivanovic"
- "matt le tissier" → "matthew le tissier"
- "thomas sørensen" → "thomas sorenson"

## Adding New Mappings

### 1. Automatic Analysis
Run the analysis tool to find new mismatches:
```bash
python3 player_name_mapper.py
```

### 2. Review Report
Check `data/player_name_mapping_report.md` for suggested mappings.

### 3. Update Dictionary
Add confirmed mappings to `NAME_MAPPING` in `player_name_mapper.py`:
```python
NAME_MAPPING = {
    "new_non_standard_name": "standard_name",
    # ... existing mappings
}
```

## Usage Examples

### In Scraping Scripts
```python
from player_name_mapper import standardize_player_name

# Before player_id matching
player_name = "Heung-min Son"
standardized = standardize_player_name(player_name)
# Result: "son heung-min"

# Use standardized name for player_id lookup
player_id = get_player_id_by_name(standardized)
```

### In Data Processing
```python
# Standardize names before merging datasets
df['standardized_name'] = df['player_name'].apply(standardize_player_name)

# Merge on player_id instead of name (more reliable)
merged_df = df1.merge(df2, on='player_id', how='left')
```

## Benefits

1. **Improved Accuracy**: Direct mapping eliminates false matches
2. **Easier Maintenance**: Simple dictionary approach
3. **Better Performance**: Direct lookup is faster than complex algorithms
4. **Centralized Data**: Pulselive data access is now centralized
5. **Consistent Merging**: player_id-based merging is more reliable

## Future Improvements

1. **Automated Mapping**: Machine learning to suggest new mappings
2. **Batch Processing**: Bulk name standardization for large datasets
3. **Validation Tools**: Automated testing of mapping accuracy
4. **Historical Tracking**: Track mapping changes over time

## File Structure

```
premier_hall/
├── player_name_mapper.py          # Direct name mapping
├── player_name_normalizer.py      # Traditional normalization
├── pulselive_data.py              # Pulselive API access
├── premier_league_awards.py       # Updated to use new system
├── player_premier_team_200.py    # Updated to use new system
└── data/
    ├── player_name_mapping_report.md  # Analysis results
    └── pulselive_player_index_appearances.csv  # Cached player data
```
