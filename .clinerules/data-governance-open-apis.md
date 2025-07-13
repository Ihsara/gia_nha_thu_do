# Data Governance Rules for Open APIs and Data Portals

## Brief overview
Mandatory data governance rules for responsible usage of open data portals and APIs, establishing procedures for respectful querying, efficient caching, and database storage to prevent unnecessary duplicate requests.

## Core Principles

### Respectful API Usage (MANDATORY)
- **Rate Limiting**: Never exceed 1 request per second to any open data portal
- **Bulk Download**: Prefer bulk data downloads over individual record queries when available
- **Cache Everything**: Store all retrieved data permanently in database tables
- **Check Database First**: Always query local database before making external API calls
- **Incremental Updates**: Only fetch new/changed data, never re-download existing records

### Database-First Strategy (REQUIRED)

#### Before Any External API Call:
1. **Check Database**: Query local database for existing data
2. **Identify Gaps**: Determine what data is missing or outdated
3. **Batch Requests**: Group missing data into efficient batch requests
4. **Respectful Timing**: Space requests appropriately (minimum 1 second intervals)
5. **Store Immediately**: Save all retrieved data to database before processing

#### Database Storage Requirements:
- **Listings Data**: All listing information must be stored in `listings` table
- **Address Data**: All geocoded addresses stored in `address_locations` table  
- **Building Data**: All building information stored in `osm_buildings` or equivalent table
- **Metadata**: Track data source, fetch timestamp, and data quality metrics
- **Deduplication**: Implement proper unique constraints to prevent duplicates

## Open Data Portal Specific Rules

### Helsinki Open Data Portal
- **Base URL**: `https://hri.fi/data/`
- **API Endpoint**: Use official API endpoints, not direct file downloads when possible
- **Rate Limit**: Maximum 1 request per 2 seconds
- **Bulk Preference**: Download datasets as complete files when size < 50MB
- **Update Frequency**: Check for updates weekly, not daily

### Finnish National Data Services
- **WFS Services**: Use GetFeature requests with appropriate BBOX and count limits
- **Spatial Queries**: Limit BBOX size to prevent server overload
- **Pagination**: Use proper WFS pagination (startIndex, count) for large datasets
- **Error Handling**: Implement exponential backoff for failed requests

### OpenStreetMap Data
- **Overpass API**: Use local caching, query reasonable bounding boxes
- **Geofabrik Extracts**: Prefer regional extracts over Overpass queries for bulk data
- **Attribution**: Always maintain proper OSM attribution in stored data
- **Update Strategy**: Monthly updates for building data, weekly for addresses

## Database Schema Requirements

### Listings Table Enhancement
```sql
-- Add data governance fields to listings table
ALTER TABLE listings ADD COLUMN IF NOT EXISTS data_source VARCHAR(50);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS fetch_timestamp TIMESTAMP;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS data_quality_score REAL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_verified TIMESTAMP;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_url TEXT;
```

### Data Lineage Tracking
```sql
-- Create data lineage table
CREATE TABLE IF NOT EXISTS data_lineage (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    data_source VARCHAR(50) NOT NULL,
    fetch_timestamp TIMESTAMP NOT NULL,
    api_endpoint TEXT,
    request_parameters JSON,
    response_metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Usage Monitoring
```sql
-- Track API usage to prevent abuse
CREATE TABLE IF NOT EXISTS api_usage_log (
    id SERIAL PRIMARY KEY,
    api_endpoint VARCHAR(200) NOT NULL,
    request_timestamp TIMESTAMP NOT NULL,
    response_status INTEGER,
    response_time_ms INTEGER,
    records_fetched INTEGER,
    rate_limit_remaining INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Implementation Standards

### Before Every External API Call (MANDATORY CHECKLIST):
- [ ] Query database for existing data first
- [ ] Calculate exact data gaps that need to be fetched
- [ ] Check last API call timestamp (enforce minimum intervals)
- [ ] Prepare batch request parameters
- [ ] Implement proper error handling and retries
- [ ] Store results immediately to database
- [ ] Log API usage for monitoring

### Code Implementation Pattern:
```python
class ResponsibleDataFetcher:
    def __init__(self):
        self.min_request_interval = 1.0  # seconds
        self.last_request_time = 0
        
    def fetch_data_responsibly(self, query_params):
        # 1. Check database first
        existing_data = self.check_database(query_params)
        if existing_data.complete:
            return existing_data
            
        # 2. Identify gaps
        missing_params = self.calculate_gaps(query_params, existing_data)
        
        # 3. Rate limiting
        self.enforce_rate_limit()
        
        # 4. Fetch missing data
        new_data = self.make_api_request(missing_params)
        
        # 5. Store immediately
        self.store_to_database(new_data)
        
        # 6. Log usage
        self.log_api_usage(missing_params, new_data)
        
        return self.combine_data(existing_data, new_data)
```

### Error Handling and Resilience:
- **Exponential Backoff**: Implement for failed requests (1s, 2s, 4s, 8s intervals)
- **Circuit Breaker**: Stop making requests after 5 consecutive failures
- **Graceful Degradation**: Use cached/existing data when APIs are unavailable
- **Monitoring**: Alert when API error rates exceed 5%

## Data Quality and Validation

### Incoming Data Validation:
- **Schema Validation**: Verify all required fields are present
- **Data Type Validation**: Ensure proper data types and formats
- **Spatial Validation**: Verify coordinates are within expected bounds
- **Duplicate Detection**: Check for existing records before insertion
- **Quality Scoring**: Assign quality scores based on completeness and accuracy

### Data Freshness Management:
- **Expiry Tracking**: Mark data with expiration dates based on source update frequency
- **Incremental Updates**: Implement smart update strategies for each data source
- **Version Control**: Track data version changes and maintain history
- **Refresh Prioritization**: Prioritize updates for frequently accessed data

## Monitoring and Compliance

### API Usage Monitoring (REQUIRED):
- **Request Volume**: Track daily/hourly request counts per API
- **Response Times**: Monitor API performance and availability
- **Error Rates**: Alert on high error rates or service disruptions
- **Rate Limit Compliance**: Ensure we never exceed stated rate limits
- **Data Freshness**: Monitor data age and update frequencies

### Compliance Reporting:
- **Usage Reports**: Generate monthly reports showing API usage patterns
- **Data Lineage**: Maintain complete audit trail for all external data
- **License Compliance**: Ensure adherence to all data license requirements
- **Attribution Tracking**: Maintain proper attribution for all data sources

### Performance Optimization:
- **Database Indexing**: Ensure proper indexes for efficient data lookups
- **Query Optimization**: Optimize database queries to minimize external API calls
- **Caching Strategy**: Implement multi-level caching (memory, disk, database)
- **Batch Processing**: Group operations to minimize overhead

## Emergency Procedures

### API Service Disruption:
- **Fallback Strategy**: Use cached data and alternative sources
- **Notification System**: Alert users when data freshness is compromised
- **Manual Override**: Procedures for manual data updates when needed
- **Recovery Planning**: Automated recovery when services are restored

### Data Corruption Detection:
- **Validation Checks**: Regular data integrity validation
- **Rollback Procedures**: Ability to restore from known good state
- **Incident Response**: Clear procedures for handling data quality issues
- **Communication Plan**: User notification procedures for data issues

This data governance framework ensures responsible, efficient, and sustainable use of open data resources while maintaining high data quality and system performance.
