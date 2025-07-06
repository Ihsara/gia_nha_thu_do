import pytest
import pandas as pd
import numpy as np

# Add the project root to the path so that we can import the dashboard logic
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the function we want to test
from oikotie.utils import extract_postal_code


@pytest.fixture
def sample_df():
    """Fixture for a sample DataFrame similar to what the dashboard uses."""
    data = {
        'city': ['Helsinki', 'Helsinki', 'Espoo', 'Helsinki'],
        'address': [
            'Mannerheimintie 1, 00100 Helsinki',
            'Fredrikinkatu 1, 00120 Helsinki',
            'Leppävaarankatu 1, 02600 Espoo',
            'Invalid Address'
        ],
        'listing_type': ['Kerrostalo', 'Kerrostalo', 'Omakotitalo', 'Kerrostalo'],
        'price_eur': [200000, 300000, 500000, 150000],
        'size_m2': [50, 70, 120, 40],
        'price_eur_per_m2': [4000, 4285.71, 4166.67, 3750]
    }
    return pd.DataFrame(data)


def test_extract_postal_code():
    assert extract_postal_code("Annankatu 1, 00100 Helsinki") == "00100"
    assert extract_postal_code("Tehtaankatu 2, 00140") == "00140"
    assert extract_postal_code("No code here") is None
    assert extract_postal_code(None) is None
    assert extract_postal_code("12345") == "12345"


def test_data_processing(sample_df):
    """Test the main data processing logic from the dashboard."""
    df = sample_df[sample_df['city'] == 'Helsinki'].copy()
    df['postal_code'] = df['address'].apply(extract_postal_code)
    df.dropna(subset=['postal_code', 'listing_type', 'price_eur_per_m2'], inplace=True)

    assert len(df) == 2  # Espoo and Invalid Address should be dropped
    assert '00100' in df['postal_code'].values
    assert '00120' in df['postal_code'].values
    assert df[df['postal_code'] == '00100']['price_eur'].iloc[0] == 200000
