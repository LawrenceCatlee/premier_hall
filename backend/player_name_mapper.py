"""
Player Name Mapper Module

This module provides a direct mapping approach for player name standardization.
Instead of complex normalization, it uses a dictionary to map non-standard names
to standard Premier League names.

Usage:
1. First run analyze_name_mismatches() to identify players with name mismatches
2. Add mappings to NAME_MAPPING dictionary
3. Use standardize_player_name() before player_id matching
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict


# Direct name mapping: "non_standard_name": "standard_name"
# This should be populated based on analysis results
NAME_MAPPING = {
    # From analysis report
    "andy cole": "andrew cole",
    "ruud van nistelrooy": "ruud van nistelrooij", 
    "petr čech": "petr cech",
    "wojciech szczęsny": "wojciech szczesny",
    "nemanja vidić": "nemanja vidic",
    "ole gunnar solskjær": "ole gunnar solskjaer",
    "i̇lkay gündoğan": "ilkay gündogan",
    "branislav ivanović": "branislav ivanovic",
    "matt le tissier": "matthew le tissier",
    "thomas sørensen": "thomas sorenson",
    "alisson": "alisson becker",
    "heung-min son": "son heung-min",
    "yakubu aiyegbeni": "yakubu",
    "andrew robertson": "andy robertson",
    "rob lee": "robert lee",
    "morten gamst pedersen": "morten pedersen",
    "tugay kerimoğlu": "tugay",
    "tomáš souček": "tomás soucek",
    "nemanja vidic‎": "nemanja vidic",
    "dirk kuyt": "dirk kuijt",
    "ken monkou": "kenneth monkou"
    
    # Add more mappings as discovered from analysis
}


def load_premier_league_players() -> pd.DataFrame:
    """Load Premier League standard player names from pulselive index"""
    try:
        df = pd.read_csv('data/pulselive_player_index_appearances.csv')
        return df[['player_id', 'player_name']].dropna()
    except FileNotFoundError:
        print("Warning: pulselive_player_index_appearances.csv not found")
        return pd.DataFrame()


def load_all_scraped_players() -> Dict[str, List[str]]:
    """Load all scraped player names from various data files"""
    scraped_players = defaultdict(list)
    
    # List of data files containing player names
    data_files = [
        'data/pl_golden_boot_winners.csv',
        'data/pl_golden_glove_winners.csv', 
        'data/pl_player_of_season_winners.csv',
        'data/pl_players_3plus_titles.csv',
        'data/pl_100_goals_club.csv',
        'data/pl_100_clean_sheets_gk.csv',
        'data/pl_team_10y_20y_award_xi.csv',
    ]
    
    for file_path in data_files:
        try:
            df = pd.read_csv(file_path)
            # Find player name columns (common column names)
            name_cols = [col for col in df.columns if 'player' in col.lower() or 'name' in col.lower()]
            
            for col in name_cols:
                for name in df[col].dropna().unique():
                    if name and str(name).strip():
                        scraped_players[file_path].append(str(name).strip())
                        
        except FileNotFoundError:
            print(f"Warning: {file_path} not found")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return scraped_players


def find_name_mismatches() -> Dict[str, Dict[str, str]]:
    """
    Analyze and find player names that don't match Premier League standard names
    Returns dictionary with file_name -> {scraped_name: closest_premier_name}
    """
    print("Analyzing name mismatches...")
    
    # Load Premier League standard names
    pl_df = load_premier_league_players()
    if pl_df.empty:
        print("No Premier League player data available")
        return {}
    
    pl_names = set(pl_df['player_name'].str.lower().str.strip())
    
    # Load scraped players
    scraped_players = load_all_scraped_players()
    
    mismatches = {}
    
    for file_path, names in scraped_players.items():
        file_mismatches = {}
        
        for name in names:
            name_lower = name.lower().strip()
            
            # Check if name exists in Premier League data
            if name_lower not in pl_names:
                # Try manual mapping first
                manual_match = manual_name_mapping(name_lower, pl_names)
                if manual_match and manual_match in pl_names:
                    file_mismatches[name] = manual_match
                else:
                    # Try to find closest match
                    closest_match = find_closest_match(name_lower, pl_names)
                    if closest_match:
                        file_mismatches[name] = closest_match
        
        if file_mismatches:
            mismatches[file_path] = file_mismatches
    
    return mismatches


def find_closest_match(target: str, candidates: set, threshold: float = 0.7) -> Optional[str]:
    """Find closest matching name using improved similarity logic"""
    from difflib import SequenceMatcher
    
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        # Calculate similarity score
        score = SequenceMatcher(None, target, candidate).ratio()
        
        # Bonus for matching last name
        target_parts = target.split()
        candidate_parts = candidate.split()
        
        if target_parts and candidate_parts:
            if target_parts[-1] == candidate_parts[-1]:
                score += 0.2  # Bonus for matching last name
        
        # Bonus for matching first name
        if len(target_parts) >= 2 and len(candidate_parts) >= 2:
            if target_parts[0] == candidate_parts[0]:
                score += 0.1  # Bonus for matching first name
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    
    return best_match


def manual_name_mapping(target: str, candidates: set) -> Optional[str]:
    """Manual mapping for common name variations"""
    target_lower = target.lower()
    
    # Common manual mappings
    manual_mappings = {
        "andy cole": "andrew cole",
        "ruud van nistelrooy": "ruud van nistelrooij", 
        "petr čech": "petr cech",
        "wojciech szczęsny": "wojciech szczesny",
        "nemanja vidić": "nemanja vidic",
        "ole gunnar solskjær": "ole gunnar solskjaer",
        "i̇lkay gündoğan": "ilkay gündogan",
        "branislav ivanović": "branislav ivanovic",
        "matt le tissier": "matthew le tissier",
        "thomas sørensen": "thomas sorenson",
        "alisson": "alisson becker",
        "heung-min son": "son heung-min",
        "yakubu aiyegbeni": "yakubu",
        "andrew robertson": "andy robertson",
        "rob lee": "robert lee",
        "morten gamst pedersen": "morten pedersen",
        "tugay kerimoğlu": "tugay",
        "tomáš souček": "tomás soucek",
        "nemanja vidic‎": "nemanja vidic",
        "dirk kuyt": "dirk kuijt",
        "ken monkou": "kenneth monkou"
    }
    
    if target_lower in manual_mappings:
        return manual_mappings[target_lower]
    
    return None


def generate_mapping_report() -> str:
    """Generate a report of all name mismatches for manual review"""
    mismatches = find_name_mismatches()
    
    if not mismatches:
        return "No name mismatches found!"
    
    report = "# Player Name Mapping Report\n\n"
    report += "## Found Name Mismatches\n\n"
    
    for file_path, file_mismatches in mismatches.items():
        report += f"### {file_path}\n\n"
        report += "| Scraped Name | Suggested Standard Name |\n"
        report += "|-------------|------------------------|\n"
        
        for scraped, standard in file_mismatches.items():
            report += f"| {scraped} | {standard} |\n"
        
        report += "\n"
    
    report += "## Recommended Mapping Code\n\n"
    report += "```python\n"
    report += "NAME_MAPPING = {\n"
    
    all_mismatches = {}
    for file_mismatches in mismatches.values():
        all_mismatches.update(file_mismatches)
    
    for scraped, standard in sorted(all_mismatches.items()):
        report += f'    \"{scraped}\": \"{standard}\",\n'
    
    report += "}\n"
    report += "```\n"
    
    return report


def standardize_player_name(name: str) -> str:
    """
    Standardize player name using direct mapping
    If name is in mapping dictionary, return standard name
    Otherwise return original name
    """
    if not name:
        return name
    
    name_lower = name.lower().strip()
    
    # Check direct mapping
    if name_lower in NAME_MAPPING:
        return NAME_MAPPING[name_lower]
    
    # Return original name if no mapping found
    return name


def add_mapping(non_standard: str, standard: str) -> None:
    """Add a new name mapping to the dictionary"""
    NAME_MAPPING[non_standard.lower().strip()] = standard.strip()


def save_mapping_report() -> str:
    """Save mapping report to file"""
    report = generate_mapping_report()
    
    output_file = Path('data/player_name_mapping_report.md')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Mapping report saved to: {output_file}")
    return str(output_file)


# Main analysis function
def analyze_name_mismatches() -> None:
    """Main function to analyze name mismatches and generate report"""
    print("=== Player Name Mismatch Analysis ===")
    
    mismatches = find_name_mismatches()
    
    if mismatches:
        total_mismatches = sum(len(file_mismatches) for file_mismatches in mismatches.values())
        print(f"Found {total_mismatches} name mismatches across {len(mismatches)} files")
        
        # Save detailed report
        report_file = save_mapping_report()
        
        # Show summary
        print("\nSummary of mismatches:")
        for file_path, file_mismatches in mismatches.items():
            print(f"  {file_path}: {len(file_mismatches)} mismatches")
        
        print(f"\nDetailed report saved to: {report_file}")
        print("Review the report and add mappings to NAME_MAPPING dictionary")
    else:
        print("✅ No name mismatches found!")


if __name__ == "__main__":
    analyze_name_mismatches()
