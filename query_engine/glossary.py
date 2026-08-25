"""Business abbreviations used by branch_analytics.xlsx.

These names are part of the data contract. Do not rename them in the
query-engine layer without changing the source-data contract first.
"""

ABBREVIATIONS = {
    'PP': 'Pre Primary',
    'PS': 'Primary School',
    'HS': 'High School',
    'E': 'Existing',
    'N': 'New',
    'LY': 'Last Year',
    'CY': 'Current Year',
    'GS': 'Grant Strength',
    'DP': 'Dropouts',
    'DPP': 'Dropouts Percentage',
    'NS': 'Net Strength',
    'STR': 'Student Teacher Ratio',
    'NSD': 'Net Strength Difference',
    'NOS': 'Number of Sections',
    'SPS': 'Students Per Section',
    'SC': 'Staff Count',
    'SD': 'Strength Difference',
    'AC': 'Activity Staff',
    'AD': 'Administration Staff',
    'NOCR': 'Number of Class Rooms',
    'NOOR': 'Number of Occupied Rooms',
    'NOVR': 'Number of Vacancy Rooms',
    'ARCS': 'Average Room Capacity Square Feet',
}

# Current first pre-function uses the overall Current Year Dropouts Percentage.
DROPOUT_PERCENTAGE_COLUMN = 'CY-DPP'
BRANCH_COLUMN = 'Branch'

# Identifier columns used by the filter-context layer (query_engine/filters.py)
# to scope a DataFrame to the dashboard's current AGM/RI/Branch/Zone selection.
AGM_COLUMN = 'AGM Name'
RI_COLUMN = 'RI Name'
ZONE_COLUMN = 'Zone'

# Segment tokens used across column parsing and parameter extraction
LEVEL_TOKENS = ('PP', 'PS', 'HS')
STAFF_CATEGORY_TOKENS = ('AC', 'AD')
TYPE_TOKENS = ('E', 'N')
YEAR_TOKENS = ('CY', 'LY')

# Metrics that live directly on a branch row with no level/type/year segments.
ROOM_METRICS = ('NOCR', 'NOOR', 'NOVR', 'ARCS')

# Metrics that inherently represent a year-over-year change.
DIFFERENCE_METRICS = ('SD', 'NSD')

# Question-side "group by" dimensions mapped to their source column.
GROUP_COLUMNS = {
    'zone': ZONE_COLUMN,
    'agm': AGM_COLUMN,
    'ri': RI_COLUMN,
}
