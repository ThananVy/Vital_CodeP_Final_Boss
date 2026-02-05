#!/usr/bin/env python3
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from scipy.spatial import cKDTree
import re
from datetime import datetime

DISTANCE_THRESHOLD_KM = 0.10
MIN_NAME_LENGTH = 3
SOURCE_FOLDER = "Original Source"
SOURCE_FILENAME = "MaterData 04-02-26.xlsx"

def split_gps_column(df):
    if 'Latitude' in df.columns and 'Longitude' in df.columns:
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        return df
    
    combined_cols = ['Mapping Coordinates', 'GPS', 'Location', 'Coordinates']
    for col_name in combined_cols:
        if col_name in df.columns:
            pattern = r'([-+]?\d*[.]\d+|\d+)[,\s]+([-+]?\d*[.]\d+|\d+)'
            extracted = df[col_name].astype(str).str.extract(pattern)
            if extracted.shape[1] >= 2:
                df['Latitude'] = pd.to_numeric(extracted[0], errors='coerce')
                df['Longitude'] = pd.to_numeric(extracted[1], errors='coerce')
                return df
    
    raise ValueError("❌ Could not detect GPS coordinates")

def normalize_name(name):
    if pd.isna(name) or str(name).strip() == '':
        return ''
    cleaned = str(name).strip()
    if re.search(r'[\u1780-\u17FF]', cleaned):
        return cleaned
    return cleaned.title()

def is_name_similar(name1, name2, min_length=MIN_NAME_LENGTH):
    n1 = normalize_name(name1).lower()
    n2 = normalize_name(name2).lower()
    if len(n1) < min_length or len(n2) < min_length:
        return False
    return (n1 in n2) or (n2 in n1)

def scale_longitude(latitude, longitude):
    return longitude * np.cos(np.radians(latitude))

def find_suspicious_pairs(df_primary, df_secondary, is_self_comparison=False):
    if len(df_primary) < 2 or len(df_secondary) < 2:
        return []
    
    secondary_scaled = np.column_stack([
        df_secondary['Latitude'].values,
        scale_longitude(df_secondary['Latitude'].values, df_secondary['Longitude'].values)
    ])
    tree = cKDTree(secondary_scaled)
    
    primary_scaled = np.column_stack([
        df_primary['Latitude'].values,
        scale_longitude(df_primary['Latitude'].values, df_primary['Longitude'].values)
    ])
    
    k = 2 if is_self_comparison else 1
    max_degrees = DISTANCE_THRESHOLD_KM * 111 * 1.5
    
    try:
        distances, indices = tree.query(primary_scaled, k=k, distance_upper_bound=max_degrees)
    except:
        return []
    
    results = []
    processed_pairs = set()
    
    for i in range(len(df_primary)):
        row_primary = df_primary.iloc[i]
        
        if pd.isna(row_primary['Customer ID']) or pd.isna(row_primary['New Shop Name']):
            continue
        
        if is_self_comparison:
            if k != 2:
                continue
            neighbor_idx = indices[i][1]
            if neighbor_idx >= len(df_secondary) or neighbor_idx == i:
                continue
        else:
            neighbor_idx = indices[i] if isinstance(indices[i], (int, np.integer)) else indices[i][0]
            if neighbor_idx >= len(df_secondary):
                continue
        
        row_secondary = df_secondary.iloc[neighbor_idx]
        if pd.isna(row_secondary['Customer ID']) or pd.isna(row_secondary['New Shop Name']):
            continue
        
        if str(row_primary['Customer ID']).strip() == str(row_secondary['Customer ID']).strip():
            continue
        
        coord_primary = (row_primary['Latitude'], row_primary['Longitude'])
        coord_secondary = (row_secondary['Latitude'], row_secondary['Longitude'])
        distance_km = geodesic(coord_primary, coord_secondary).kilometers
        
        if distance_km > DISTANCE_THRESHOLD_KM:
            continue
        
        if not is_name_similar(row_primary['New Shop Name'], row_secondary['New Shop Name']):
            continue
        
        id_a = str(row_primary['Customer ID']).strip()
        id_b = str(row_secondary['Customer ID']).strip()
        pair_key = '|'.join(sorted([id_a, id_b]))
        if pair_key in processed_pairs:
            continue
        processed_pairs.add(pair_key)
        
        comparison_type = 'Secured vs Secured' if is_self_comparison and df_primary['is_secured'].iloc[0] else \
                         'Unsecured vs Unsecured' if is_self_comparison else 'Unsecured vs Secured'
        
        results.append({
            'Customer ID A': id_a,
            'Shop Name A': normalize_name(row_primary['New Shop Name']),
            'Prospect Code A': str(row_primary['Prospect Code']).strip() if pd.notna(row_primary['Prospect Code']) else '',
            'Latitude A': row_primary['Latitude'],
            'Longitude A': row_primary['Longitude'],
            'Customer ID B': id_b,
            'Shop Name B': normalize_name(row_secondary['New Shop Name']),
            'Prospect Code B': str(row_secondary['Prospect Code']).strip() if pd.notna(row_secondary['Prospect Code']) else '',
            'Latitude B': row_secondary['Latitude'],
            'Longitude B': row_secondary['Longitude'],
            'Distance (km)': round(distance_km, 3),
            'Names Similar': True,
            'Suspicious Duplicate': True,
            'Comparison Type': comparison_type
        })
    
    return results

def main(mode='all'):
    print("\n" + "="*70)
    print("DUPLICATE DETECTION ENGINE - PRODUCTION READY")
    print("="*70)
    
    source_path = Path(SOURCE_FOLDER) / SOURCE_FILENAME
    if not source_path.exists():
        print(f"\n❌ File not found: {source_path}")
        sys.exit(1)
    
    print(f"\n📁 Loading: {source_path}")
    df = pd.read_excel(source_path, dtype=str)
    print(f"   → Total rows: {len(df):,}")
    print(f"   → Columns: {list(df.columns)}")
    
    print("\n🌍 Parsing GPS coordinates...")
    df = split_gps_column(df)
    initial_count = len(df)
    df = df.dropna(subset=['Latitude', 'Longitude']).copy()
    print(f"   → Valid coordinates: {len(df):,} (dropped {initial_count - len(df):,})")
    
    print("\n🛡️  Classifying secured/unsecured shops...")
    df['Prospect Code'] = df['Prospect Code'].replace(['nan', 'NaN', 'None', ''], np.nan)
    df['is_secured'] = df['Prospect Code'].notna() & (df['Prospect Code'].str.strip() != '')
    
    secured = df[df['is_secured']].copy().reset_index(drop=True)
    unsecured = df[~df['is_secured']].copy().reset_index(drop=True)
    
    print(f"   → SECURED shops:   {len(secured):,} (Prospect Code populated)")
    if len(secured) > 0:
        sample_codes = secured['Prospect Code'].head(3).tolist()
        print(f"      Sample codes: {sample_codes}")
    print(f"   → UNSECURED shops: {len(unsecured):,} (Prospect Code empty/blank)")
    
    all_results = []
    
    if mode in ['all', 'secured'] and len(secured) >= 2:
        print("\n🔍 Secured vs Secured comparison...")
        results = find_suspicious_pairs(secured, secured, True)
        all_results.extend(results)
        print(f"   → Found {len(results)} suspicious pairs")
    
    if mode in ['all', 'unsecured_secured'] and len(unsecured) > 0 and len(secured) > 0:
        print("\n🔍 Unsecured vs Secured comparison...")
        results = find_suspicious_pairs(unsecured, secured, False)
        all_results.extend(results)
        print(f"   → Found {len(results)} suspicious pairs")
    
    if mode in ['all', 'unsecured'] and len(unsecured) >= 2:
        print("\n🔍 Unsecured vs Unsecured comparison...")
        results = find_suspicious_pairs(unsecured, unsecured, True)
        all_results.extend(results)
        print(f"   → Found {len(results)} suspicious pairs")
    
    timestamp = datetime.now().strftime("%d-%m-%y")
    output_filename = f"duplicate_analysis_{mode}_{timestamp}.xlsx"
    
    if all_results:
        result_df = pd.DataFrame(all_results)
        result_df['Pair_ID'] = result_df.apply(
            lambda row: '|'.join(sorted([str(row['Customer ID A']).strip(), str(row['Customer ID B']).strip()])),
            axis=1
        )
        result_df = result_df.drop_duplicates(subset=['Pair_ID']).drop(columns=['Pair_ID'])
        result_df = result_df.sort_values('Distance (km)').reset_index(drop=True)
        
        column_order = [
            'Customer ID A', 'Shop Name A', 'Prospect Code A', 'Latitude A', 'Longitude A',
            'Customer ID B', 'Shop Name B', 'Prospect Code B', 'Latitude B', 'Longitude B',
            'Distance (km)', 'Names Similar', 'Suspicious Duplicate', 'Comparison Type'
        ]
        result_df = result_df[[col for col in column_order if col in result_df.columns]]
        
        result_df.to_excel(output_filename, index=False)
        print(f"\n✅ SUCCESS: Saved {len(result_df)} suspicious pairs to '{output_filename}'")
        print("\n📊 Top 5 results (non-blank):")
        preview = result_df[['Customer ID A', 'Shop Name A', 'Customer ID B', 'Shop Name B', 'Distance (km)', 'Comparison Type']].head()
        print(preview.to_string(index=False))
    else:
        print(f"\nℹ️  No suspicious pairs found for mode '{mode}'")
        print(f"\n💡 Tips:")
        print(f"   • Try lowering DISTANCE_THRESHOLD_KM (line 10) to 0.20 for 200m sensitivity")
        print(f"   • Run 'unsecured' mode if most shops lack Prospect Code")
        print(f"   • Check shop name consistency (e.g., 'ABC Mart' vs 'ABC Mart #2')")
    
    print("\n" + "="*70)
    print(f"Output: {output_filename} | Total pairs: {len(all_results)}")
    print("="*70 + "\n")

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    main(mode.lower())