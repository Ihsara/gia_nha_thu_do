# Database Connection Bugs

## Bug Frequency Analysis
### Weekly Summary (Updated Every Friday)
- **New Bugs**: 0 discovered this week
- **Fixed Bugs**: 0 resolved this week
- **Recurring Bugs**: 0 previously seen bugs that reoccurred
- **Critical Open**: 0 critical bugs still open

### Monthly Trends
- **Most Frequent Category**: No data yet
- **Resolution Time Average**: No data yet
- **Prevention Effectiveness**: No data yet

## Bug Categories Tracked

### DuckDB Connection Bugs
- Database file access failures
- Connection timeout errors
- Concurrent access conflicts
- Database lock issues
- Permission and file system errors

### SQL Query Bugs
- Syntax errors in complex queries
- Invalid column or table references
- JOIN operation failures
- Aggregation and grouping errors
- Query execution timeout

### Data Type Conversion Bugs
- Geometry data conversion failures
- Date/time parsing errors
- Numeric precision issues
- String encoding problems
- NULL value handling errors

### Table Schema Bugs
- Column name mismatches
- Data type incompatibilities
- Primary key constraint violations
- Foreign key relationship errors
- Index creation and usage failures

### Cache Loading Bugs
- Cache file corruption
- Cache invalidation failures
- Memory overflow from large caches
- Cache key collision issues
- Partial cache loading errors

## Recent Bug Entries

*No bugs documented yet. When database connection bugs are discovered, they will be documented here using the mandatory bug entry format from the error documentation system.*

## Common Symptoms to Watch For

### Connection Failures
```
Error: Database file not found: data/real_estate.duckdb
Error: Permission denied accessing database file
Error: Database is locked by another process
ConnectionError: Failed to establish database connection
```

### Query Execution Errors
```
SQL Error: column "invalid_column" does not exist
Error: syntax error near line X
Error: JOIN condition failed - no matching records
Error: Query timeout after 30 seconds
```

### Data Type Issues
```
TypeError: Cannot convert geometry to string
ValueError: Invalid date format in column
Error: Numeric overflow in aggregation
UnicodeDecodeError: Invalid string encoding
```

### Schema Problems
```
Error: Table 'missing_table' does not exist
Error: Column count mismatch in INSERT
Error: Primary key constraint violation
Error: Foreign key reference not found
```

### Cache Related Errors
```
Error: Cache file corrupted or unreadable
MemoryError: Cache size exceeds available memory
Error: Cache key generation failed
Warning: Cache validation failed, rebuilding
```

## Prevention Strategies

### Connection Management
- Implement connection pooling and retry logic
- Validate database file existence before connecting
- Handle concurrent access with proper locking
- Monitor database file permissions and ownership

### Query Validation
- Validate SQL syntax before execution
- Check table and column existence dynamically
- Implement query timeout handling
- Use parameterized queries to prevent injection

### Data Type Safety
- Implement strict data type validation
- Handle NULL values explicitly in queries
- Use appropriate data type conversions
- Validate geometry data before database operations

### Schema Management
- Maintain schema documentation and validation
- Implement database migration procedures
- Validate foreign key relationships
- Monitor and alert on schema drift

### Cache Optimization
- Implement cache size limits and monitoring
- Use cache validation and integrity checks
- Implement cache eviction policies
- Handle cache corruption gracefully

## Known Database Context

### Current DuckDB Schema (data/real_estate.duckdb)
- **listings** (8,725 rows) - Real estate listings data
- **osm_buildings** (79,556 rows) - OpenStreetMap buildings
- **address_locations** (6,643 rows) - Address geocoding data
- **Helsinki administrative tables** - Property boundaries and markers

### Key Relationships
- `listings.address` → `address_locations.address`
- Spatial joins between listings and osm_buildings
- Geographic relationships with Helsinki administrative boundaries

### Common Query Patterns to Test
- Spatial joins with geometry operations
- Address matching and geocoding queries
- Aggregation queries for dashboard statistics
- Complex filtering with multiple JOIN operations

---

*This file tracks all database access, query execution, and data management bugs encountered in the Oikotie project.*
