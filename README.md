# Vital_CodeP_Final_Boss

Automated duplicate detection for customer/shop records using geospatial proximity and name similarity analysis.

---

## 📥 Required Input Columns

| Column | Required | Description | Format Notes |
|--------|----------|-------------|--------------|
| `Customer ID` | ✅ Yes | Unique customer identifier | Text (no duplicates within source) |
| `New Shop Name` | ✅ Yes | Shop/business name | Supports Khmer/English Unicode |
| `Prospect Code` | ✅ Yes | Security classification field | Non-blank = **Secured**<br>Blank/NaN = **Unsecured** |
| GPS Data | ✅ Yes | Location coordinates | **Option A:** Separate `Latitude` + `Longitude` columns<br>**Option B:** Combined column named `Mapping Coordinates`, `GPS`, `Location`, or `Coordinates` (e.g., `"11.5624, 104.9160"`) |

> ⚠️ **Critical**: All GPS values must be numeric decimals. Script auto-extracts from combined formats but fails if coordinates are missing/invalid.

---

## ⚙️ Core Detection Logic

### Step 1: Classification
- **Secured shops**: `Prospect Code` populated (non-blank)
- **Unsecured shops**: `Prospect Code` empty/blank/NaN

### Step 2: Pairwise Comparison (3 modes)
| Comparison Type | Trigger Condition |
|-----------------|-------------------|
| Secured vs Secured | Distance ≤ **0.10 km** (100m) + Name similarity |
| Unsecured vs Secured | Distance ≤ **0.10 km** (100m) + Name similarity |
| Unsecured vs Unsecured | Distance ≤ **0.10 km** (100m) + Name similarity |

### Step 3: Matching Rules
| Rule | Logic |
|------|-------|
| **GPS Proximity** | Haversine distance ≤ 0.10 km (100 meters) |
| **Name Similarity** | One shop name is substring of the other (case-insensitive, after Unicode normalization) |
| **Exclusion** | Same `Customer ID` → automatically skipped |

---

## 📤 Output Structure (`duplicate_analysis_*.xlsx`)

| Column Group | Fields | Purpose |
|--------------|--------|---------|
| **Record A** | `Customer ID A`, `Shop Name A`, `Prospect Code A`, `Latitude A`, `Longitude A` | First record in suspicious pair |
| **Record B** | `Customer ID B`, `Shop Name B`, `Prospect Code B`, `Latitude B`, `Longitude B` | Second record in suspicious pair |
| **Analysis** | `Distance (km)`, `Names Similar`, `Suspicious Duplicate`, `Comparison Type` | Verification metrics |

### Key Output Behaviors
- ✅ **Deduplicated pairs**: Each unique pair appears only once (sorted by Customer ID)
- ✅ **Sorted results**: Closest matches first (`Distance (km)` ascending)
- ✅ **Audit-ready**: Full coordinate/name details for manual verification
- ❌ **No auto-merging**: Script **flags** duplicates only — human review required before deactivation

---

## 📊 Expected Result Example

| Customer ID A | Shop Name A | Customer ID B | Shop Name B | Distance (km) | Comparison Type |
|---------------|-------------|---------------|-------------|---------------|-----------------|
| CUS-1001 | ហាងកាហ្វេភ្នំពេញ | CUS-2045 | កាហ្វេភ្នំពេញ | 0.042 | Secured vs Secured |
| CUS-3089 | ABC Mart #2 | CUS-4112 | ABC Mart | 0.087 | Unsecured vs Secured |

> 🔍 **Interpretation**:  
> - Pair 1: Khmer names share substring `"កាហ្វេភ្នំពេញ"` at 42m distance → **high-confidence duplicate**  
> - Pair 2: English names share `"ABC Mart"` at 87m distance → **requires manual verification** (could be legitimate nearby branches)
