# Player Name Mapping Report

## Found Name Mismatches

### data/pl_golden_boot_winners.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Andy Cole | andrew cole |
| Ruud van Nistelrooy | ruud van nistelrooij |

### data/pl_golden_glove_winners.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Petr Čech | petr cech |
| Wojciech Szczęsny | wojciech szczesny |
| Alisson | alisson becker |

### data/pl_player_of_season_winners.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Ruud van Nistelrooy | ruud van nistelrooij |
| Nemanja Vidić | nemanja vidic |

### data/pl_players_3plus_titles.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Ole Gunnar Solskjær | ole gunnar solskjaer |
| Andy Cole | andrew cole |
| Nemanja Vidić | nemanja vidic |
| İlkay Gündoğan | ilkay gündogan |
| Petr Čech | petr cech |
| Branislav Ivanović | branislav ivanovic |

### data/pl_100_goals_club.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Andy Cole | andrew cole |
| Heung-min Son | son heung-min |
| Matt Le Tissier | matthew le tissier |
| Yakubu Aiyegbeni | yakubu |
| Ruud van Nistelrooy | ruud van nistelrooij |

### data/pl_100_clean_sheets_gk.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Thomas Sörensen | thomas sørensen |
| Alisson | alisson becker |

### data/pl_team_10y_20y_award_xi.csv

| Scraped Name | Suggested Standard Name |
|-------------|------------------------|
| Nemanja Vidić | nemanja vidic |

## Recommended Mapping Code

```python
NAME_MAPPING = {
    "Alisson": "alisson becker",
    "Andy Cole": "andrew cole",
    "Branislav Ivanović": "branislav ivanovic",
    "Heung-min Son": "son heung-min",
    "Matt Le Tissier": "matthew le tissier",
    "Nemanja Vidić": "nemanja vidic",
    "Ole Gunnar Solskjær": "ole gunnar solskjaer",
    "Petr Čech": "petr cech",
    "Ruud van Nistelrooy": "ruud van nistelrooij",
    "Thomas Sörensen": "thomas sørensen",
    "Wojciech Szczęsny": "wojciech szczesny",
    "Yakubu Aiyegbeni": "yakubu",
    "İlkay Gündoğan": "ilkay gündogan",
}
```
