"""
Coordinate Bounds Validation for Multi-City Support

This module provides coordinate validation functions for Helsinki and Espoo,
ensuring that property listings have valid coordinates within city boundaries.
"""

import duckdb
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger
from enum import Enum


class ValidationStatus(Enum):
    """Coordinate validation status"""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    ERROR = "error"


@dataclass
class CityBounds:
    """City coordinate bounds definition"""
    name: str
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float
    
    def contains_point(self, latitude: float, longitude: float) -> bool:
        """Check if coordinates are within city bounds"""
        return (self.min_latitude <= latitude <= self.max_latitude and
                self.min_longitude <= longitude <= self.max_longitude)


@dataclass
class ValidationResult:
    """Result of coordinate validation"""
    is_valid: bool
    status: ValidationStatus
    error_message: Optional[str] = None
    city_bounds: Optional[CityBounds] = None


class CoordinateValidator:
    """Coordinate validation for multi-city support"""
    
    def __init__(self, db_path: str = "data/real_estate.duckdb"):
        self.db_path = db_path
        self.city_bounds = self._define_city_bounds()
    
    def _define_city_bounds(self) -> Dict[str, CityBounds]:
        """Define coordinate bounds for supported cities"""
        return {
            'Helsinki': CityBounds(
                name='Helsinki',
                min_latitude=60.0,
                max_latitude=60.5,
                min_longitude=24.5,
                max_longitude=25.5
            ),
            'Espoo': CityBounds(
                name='Espoo',
                min_latitude=60.1,
                max_latitude=60.4,
                min_longitude=24.4,
                max_longitude=24.9
            )
        }
    
    def validate_coordinates(self, city: str, latitude: float, longitude: float) -> ValidationResult:
        """Validate coordinates for a specific city"""
        # Check if city is supported
        if city not in self.city_bounds:
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.ERROR,
                error_message=f"Unsupported city: {city}. Supported cities: {list(self.city_bounds.keys())}"
            )
        
        # Check for valid coordinate values
        if latitude is None or longitude is None:
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.ERROR,
                error_message="Latitude or longitude is None"
            )
        
        # Check coordinate ranges (basic sanity check)
        if not (-90 <= latitude <= 90):
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.ERROR,
                error_message=f"Invalid latitude: {latitude} (must be between -90 and 90)"
            )
        
        if not (-180 <= longitude <= 180):
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.ERROR,
                error_message=f"Invalid longitude: {longitude} (must be between -180 and 180)"
            )
        
        # Check city bounds
        bounds = self.city_bounds[city]
        if bounds.contains_point(latitude, longitude):
            return ValidationResult(
                is_valid=True,
                status=ValidationStatus.VALID,
                city_bounds=bounds
            )
        else:
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                error_message=f"Coordinates ({latitude}, {longitude}) outside {city} bounds "
                            f"(lat: {bounds.min_latitude}-{bounds.max_latitude}, "
                            f"lon: {bounds.min_longitude}-{bounds.max_longitude})",
                city_bounds=bounds
            )
    
    def validate_listing_coordinates(self, listing_data: Dict) -> ValidationResult:
        """Validate coordinates for a listing dictionary"""
        city = listing_data.get('city')
        latitude = listing_data.get('latitude')
        longitude = listing_data.get('longitude')
        
        return self.validate_coordinates(city, latitude, longitude)
    
    def batch_validate_coordinates(self, listings: List[Dict]) -> Dict[str, ValidationResult]:
        """Validate coordinates for multiple listings"""
        results = {}
        
        for listing in listings:
            url = listing.get('url', 'unknown')
            result = self.validate_listing_coordinates(listing)
            results[url] = result
        
        return results
    
    def update_database_validation(self, batch_size: int = 1000) -> Dict[str, int]:
        """Update coordinate validation status in database"""
        logger.info("Starting database coordinate validation update")
        
        stats = {
            'total_processed': 0,
            'valid_coordinates': 0,
            'invalid_coordinates': 0,
            'error_coordinates': 0,
            'updated_records': 0
        }
        
        try:
            with duckdb.connect(self.db_path) as con:
                # Get listings that need validation
                listings = con.execute("""
                    SELECT url, city, latitude, longitude 
                    FROM listings 
                    WHERE city IS NOT NULL 
                      AND latitude IS NOT NULL 
                      AND longitude IS NOT NULL
                      AND (city_validated IS NULL OR last_coordinate_validation IS NULL)
                    ORDER BY scraped_at DESC
                """).fetchall()
                
                logger.info(f"Found {len(listings)} listings to validate")
                
                # Process in batches
                for i in range(0, len(listings), batch_size):
                    batch = listings[i:i + batch_size]
                    
                    for url, city, lat, lon in batch:
                        result = self.validate_coordinates(city, lat, lon)
                        
                        # Update database record
                        con.execute("""
                            UPDATE listings 
                            SET city_validated = ?,
                                coordinate_validation_error = ?,
                                last_coordinate_validation = CURRENT_TIMESTAMP,
                                geospatial_quality_score = ?
                            WHERE url = ?
                        """, [
                            result.is_valid,
                            result.error_message,
                            1.0 if result.is_valid else 0.0,
                            url
                        ])
                        
                        # Update statistics
                        stats['total_processed'] += 1
                        stats['updated_records'] += 1
                        
                        if result.status == ValidationStatus.VALID:
                            stats['valid_coordinates'] += 1
                        elif result.status == ValidationStatus.INVALID:
                            stats['invalid_coordinates'] += 1
                        else:
                            stats['error_coordinates'] += 1
                    
                    if i % (batch_size * 10) == 0:
                        logger.info(f"Processed {i + len(batch)} / {len(listings)} listings")
                
                logger.success(f"Coordinate validation completed: {stats}")
                
        except Exception as e:
            logger.error(f"Database validation update failed: {e}")
            raise
        
        return stats
    
    def get_validation_summary(self) -> Dict[str, Dict]:
        """Get validation summary by city"""
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                summary = {}
                
                # Get validation statistics by city
                results = con.execute("""
                    SELECT 
                        city,
                        COUNT(*) as total_listings,
                        COUNT(CASE WHEN city_validated = TRUE THEN 1 END) as valid_count,
                        COUNT(CASE WHEN city_validated = FALSE THEN 1 END) as invalid_count,
                        COUNT(CASE WHEN city_validated IS NULL THEN 1 END) as pending_count,
                        AVG(geospatial_quality_score) as avg_quality_score,
                        COUNT(CASE WHEN coordinate_validation_error IS NOT NULL THEN 1 END) as error_count
                    FROM listings 
                    WHERE city IS NOT NULL
                    GROUP BY city
                """).fetchall()
                
                for row in results:
                    city, total, valid, invalid, pending, avg_quality, errors = row
                    summary[city] = {
                        'total_listings': total,
                        'valid_coordinates': valid,
                        'invalid_coordinates': invalid,
                        'pending_validation': pending,
                        'validation_errors': errors,
                        'validation_rate': (valid / total * 100) if total > 0 else 0,
                        'avg_quality_score': avg_quality or 0.0
                    }
                
                return summary
                
        except Exception as e:
            logger.error(f"Failed to get validation summary: {e}")
            return {}
    
    def get_invalid_coordinates(self, city: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get listings with invalid coordinates"""
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                query = """
                    SELECT url, city, address, latitude, longitude, coordinate_validation_error
                    FROM listings 
                    WHERE city_validated = FALSE
                """
                params = []
                
                if city:
                    query += " AND city = ?"
                    params.append(city)
                
                query += f" ORDER BY last_coordinate_validation DESC LIMIT {limit}"
                
                results = con.execute(query, params).fetchall()
                
                return [
                    {
                        'url': row[0],
                        'city': row[1],
                        'address': row[2],
                        'latitude': row[3],
                        'longitude': row[4],
                        'error': row[5]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Failed to get invalid coordinates: {e}")
            return []
    
    def create_validation_report(self, output_path: str = None) -> str:
        """Create a detailed validation report"""
        if output_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"coordinate_validation_report_{timestamp}.md"
        
        summary = self.get_validation_summary()
        
        report_lines = [
            "# Coordinate Validation Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Summary by City",
            ""
        ]
        
        for city, stats in summary.items():
            report_lines.extend([
                f"### {city}",
                f"- Total listings: {stats['total_listings']:,}",
                f"- Valid coordinates: {stats['valid_coordinates']:,} ({stats['validation_rate']:.1f}%)",
                f"- Invalid coordinates: {stats['invalid_coordinates']:,}",
                f"- Pending validation: {stats['pending_validation']:,}",
                f"- Validation errors: {stats['validation_errors']:,}",
                f"- Average quality score: {stats['avg_quality_score']:.3f}",
                ""
            ])
        
        # Add city bounds information
        report_lines.extend([
            "## City Coordinate Bounds",
            ""
        ])
        
        for city, bounds in self.city_bounds.items():
            report_lines.extend([
                f"### {city}",
                f"- Latitude: {bounds.min_latitude} to {bounds.max_latitude}",
                f"- Longitude: {bounds.min_longitude} to {bounds.max_longitude}",
                ""
            ])
        
        # Add sample invalid coordinates
        report_lines.extend([
            "## Sample Invalid Coordinates",
            ""
        ])
        
        for city in self.city_bounds.keys():
            invalid_coords = self.get_invalid_coordinates(city, limit=5)
            if invalid_coords:
                report_lines.extend([
                    f"### {city} - Invalid Coordinates",
                    ""
                ])
                for coord in invalid_coords:
                    report_lines.append(f"- {coord['address']}: ({coord['latitude']}, {coord['longitude']}) - {coord['error']}")
                report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Validation report saved to: {output_path}")
        return report_content


def validate_city_coordinates_function(city: str, latitude: float, longitude: float) -> bool:
    """Standalone function for coordinate validation (for SQL function)"""
    validator = CoordinateValidator()
    result = validator.validate_coordinates(city, latitude, longitude)
    return result.is_valid


def run_coordinate_validation():
    """Run coordinate validation for all listings"""
    validator = CoordinateValidator()
    stats = validator.update_database_validation()
    summary = validator.get_validation_summary()
    
    logger.info("Coordinate validation completed")
    logger.info(f"Processing stats: {stats}")
    logger.info(f"Validation summary: {summary}")
    
    return stats, summary