"""
Database Models for Oikotie Real Estate Project

This module provides data class definitions for major entities,
validation utilities, and conversion functions for database operations.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from datetime import date
from decimal import Decimal
import json
from pathlib import Path


@dataclass
class Listing:
    """Real estate listing data model"""
    address: str
    latitude: float
    longitude: float
    price: Optional[float] = None
    listing_type: Optional[str] = None
    listing_date: Optional[date] = None
    geometry_wkt: Optional[str] = None
    
    def __post_init__(self):
        """Validate listing data after initialization"""
        self.validate()
    
    def validate(self) -> None:
        """Validate listing data constraints"""
        # Coordinate bounds for Helsinki metropolitan area
        if not (60.0 <= self.latitude <= 60.5):
            raise ValueError(f"Latitude {self.latitude} outside Helsinki bounds (60.0-60.5)")
        
        if not (24.5 <= self.longitude <= 25.5):
            raise ValueError(f"Longitude {self.longitude} outside Helsinki bounds (24.5-25.5)")
        
        # Price validation
        if self.price is not None and self.price <= 0:
            raise ValueError(f"Price {self.price} must be positive")
        
        # Address validation
        if not self.address or not self.address.strip():
            raise ValueError("Address cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            'address': self.address,
            'price': self.price,
            'listing_type': self.listing_type,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'listing_date': self.listing_date,
            'geometry': f"POINT({self.longitude} {self.latitude})" if self.geometry_wkt is None else self.geometry_wkt
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Listing':
        """Create Listing from dictionary/database row"""
        return cls(
            address=data['address'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            price=float(data['price']) if data.get('price') is not None else None,
            listing_type=data.get('listing_type'),
            listing_date=data.get('listing_date'),
            geometry_wkt=data.get('geometry')
        )


@dataclass
class OSMBuilding:
    """OpenStreetMap building data model"""
    osm_id: int
    geometry_wkt: str
    building_type: Optional[str] = None
    name: Optional[str] = None
    addr_street: Optional[str] = None
    addr_housenumber: Optional[str] = None
    addr_postcode: Optional[str] = None
    
    def __post_init__(self):
        """Validate building data after initialization"""
        self.validate()
    
    def validate(self) -> None:
        """Validate building data constraints"""
        if self.osm_id <= 0:
            raise ValueError(f"OSM ID {self.osm_id} must be positive")
        
        if not self.geometry_wkt or not self.geometry_wkt.strip():
            raise ValueError("Geometry WKT cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            'osm_id': self.osm_id,
            'geometry': self.geometry_wkt,
            'building_type': self.building_type,
            'name': self.name,
            'addr_street': self.addr_street,
            'addr_housenumber': self.addr_housenumber,
            'addr_postcode': self.addr_postcode
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OSMBuilding':
        """Create OSMBuilding from dictionary/database row"""
        return cls(
            osm_id=int(data['osm_id']),
            geometry_wkt=data['geometry'],
            building_type=data.get('building_type'),
            name=data.get('name'),
            addr_street=data.get('addr_street'),
            addr_housenumber=data.get('addr_housenumber'),
            addr_postcode=data.get('addr_postcode')
        )
    
    def get_full_address(self) -> Optional[str]:
        """Get full address string if available"""
        if self.addr_street and self.addr_housenumber:
            address_parts = [self.addr_street, self.addr_housenumber]
            if self.addr_postcode:
                address_parts.append(self.addr_postcode)
            return " ".join(address_parts)
        return None


@dataclass
class AddressLocation:
    """Address location data model"""
    address: str
    latitude: float
    longitude: float
    postcode: Optional[str] = None
    district: Optional[str] = None
    geometry_wkt: Optional[str] = None
    
    def __post_init__(self):
        """Validate address data after initialization"""
        self.validate()
    
    def validate(self) -> None:
        """Validate address location data constraints"""
        # Coordinate bounds for Helsinki metropolitan area
        if not (60.0 <= self.latitude <= 60.5):
            raise ValueError(f"Latitude {self.latitude} outside Helsinki bounds (60.0-60.5)")
        
        if not (24.5 <= self.longitude <= 25.5):
            raise ValueError(f"Longitude {self.longitude} outside Helsinki bounds (24.5-25.5)")
        
        # Address validation
        if not self.address or not self.address.strip():
            raise ValueError("Address cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'postcode': self.postcode,
            'district': self.district,
            'geometry': f"POINT({self.longitude} {self.latitude})" if self.geometry_wkt is None else self.geometry_wkt
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AddressLocation':
        """Create AddressLocation from dictionary/database row"""
        return cls(
            address=data['address'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            postcode=data.get('postcode'),
            district=data.get('district'),
            geometry_wkt=data.get('geometry')
        )


@dataclass
class PropertyBoundary:
    """Helsinki property boundary data model"""
    boundary_id: str
    geometry_wkt: str
    boundary_type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate boundary data after initialization"""
        self.validate()
    
    def validate(self) -> None:
        """Validate property boundary data constraints"""
        if not self.boundary_id or not self.boundary_id.strip():
            raise ValueError("Boundary ID cannot be empty")
        
        if not self.geometry_wkt or not self.geometry_wkt.strip():
            raise ValueError("Geometry WKT cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            'boundary_id': self.boundary_id,
            'boundary_type': self.boundary_type,
            'geometry': self.geometry_wkt,
            'properties': json.dumps(self.properties) if self.properties else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PropertyBoundary':
        """Create PropertyBoundary from dictionary/database row"""
        properties = None
        if data.get('properties'):
            try:
                properties = json.loads(data['properties']) if isinstance(data['properties'], str) else data['properties']
            except (json.JSONDecodeError, TypeError):
                properties = None
        
        return cls(
            boundary_id=data['boundary_id'],
            geometry_wkt=data['geometry'],
            boundary_type=data.get('boundary_type'),
            properties=properties
        )


@dataclass
class AdminMarker:
    """Helsinki administrative marker data model"""
    marker_id: str
    geometry_wkt: str
    marker_type: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate marker data after initialization"""
        self.validate()
    
    def validate(self) -> None:
        """Validate admin marker data constraints"""
        if not self.marker_id or not self.marker_id.strip():
            raise ValueError("Marker ID cannot be empty")
        
        if not self.geometry_wkt or not self.geometry_wkt.strip():
            raise ValueError("Geometry WKT cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            'marker_id': self.marker_id,
            'marker_type': self.marker_type,
            'geometry': self.geometry_wkt,
            'properties': json.dumps(self.properties) if self.properties else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdminMarker':
        """Create AdminMarker from dictionary/database row"""
        properties = None
        if data.get('properties'):
            try:
                properties = json.loads(data['properties']) if isinstance(data['properties'], str) else data['properties']
            except (json.JSONDecodeError, TypeError):
                properties = None
        
        return cls(
            marker_id=data['marker_id'],
            geometry_wkt=data['geometry'],
            marker_type=data.get('marker_type'),
            properties=properties
        )


@dataclass
class SpatialJoinResult:
    """Result of spatial join operations between listings and buildings"""
    listing_address: str
    listing_lat: float
    listing_lon: float
    building_osm_id: Optional[int] = None
    building_type: Optional[str] = None
    building_name: Optional[str] = None
    spatial_relationship: Optional[str] = None
    distance_meters: Optional[float] = None
    
    def is_matched(self) -> bool:
        """Check if listing has a spatial match with a building"""
        return self.building_osm_id is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for analysis and export"""
        return {
            'listing_address': self.listing_address,
            'listing_lat': self.listing_lat,
            'listing_lon': self.listing_lon,
            'building_osm_id': self.building_osm_id,
            'building_type': self.building_type,
            'building_name': self.building_name,
            'spatial_relationship': self.spatial_relationship,
            'distance_meters': self.distance_meters,
            'is_matched': self.is_matched()
        }


@dataclass 
class ValidationResult:
    """Result of data validation operations"""
    total_records: int
    valid_records: int
    invalid_records: int
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def validation_rate(self) -> float:
        """Calculate validation success rate as percentage"""
        if self.total_records == 0:
            return 0.0
        return (self.valid_records / self.total_records) * 100
    
    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)"""
        return len(self.validation_errors) == 0
    
    def add_error(self, error: str) -> None:
        """Add validation error"""
        self.validation_errors.append(error)
        self.invalid_records += 1
    
    def add_warning(self, warning: str) -> None:
        """Add validation warning"""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting"""
        return {
            'total_records': self.total_records,
            'valid_records': self.valid_records,
            'invalid_records': self.invalid_records,
            'validation_rate': self.validation_rate,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors,
            'warnings': self.warnings
        }


# Model registry for dynamic model access
MODEL_REGISTRY = {
    'listings': Listing,
    'osm_buildings': OSMBuilding,
    'address_locations': AddressLocation,
    'helsinki_property_boundaries': PropertyBoundary,
    'helsinki_admin_markers': AdminMarker
}


def get_model_class(table_name: str):
    """Get model class for a given table name"""
    return MODEL_REGISTRY.get(table_name)


def validate_model_data(model_class, data: Dict[str, Any]) -> ValidationResult:
    """Validate data against model class constraints"""
    result = ValidationResult(total_records=1, valid_records=0, invalid_records=0)
    
    try:
        # Attempt to create model instance (triggers validation)
        instance = model_class.from_dict(data)
        result.valid_records = 1
    except (ValueError, TypeError, KeyError) as e:
        result.add_error(f"Validation failed: {str(e)}")
    
    return result


def batch_validate_model_data(model_class, data_list: List[Dict[str, Any]]) -> ValidationResult:
    """Validate a batch of data records against model class constraints"""
    result = ValidationResult(total_records=len(data_list), valid_records=0, invalid_records=0)
    
    for i, data in enumerate(data_list):
        try:
            # Attempt to create model instance (triggers validation)
            instance = model_class.from_dict(data)
            result.valid_records += 1
        except (ValueError, TypeError, KeyError) as e:
            result.add_error(f"Record {i+1}: {str(e)}")
    
    return result


def convert_to_model_instances(table_name: str, data_list: List[Dict[str, Any]]) -> List[Any]:
    """Convert list of dictionaries to model instances"""
    model_class = get_model_class(table_name)
    if not model_class:
        raise ValueError(f"No model class found for table: {table_name}")
    
    instances = []
    for data in data_list:
        try:
            instance = model_class.from_dict(data)
            instances.append(instance)
        except (ValueError, TypeError, KeyError) as e:
            # Skip invalid records with warning
            print(f"Warning: Skipping invalid record: {e}")
            continue
    
    return instances


def convert_from_model_instances(instances: List[Any]) -> List[Dict[str, Any]]:
    """Convert list of model instances to dictionaries"""
    return [instance.to_dict() for instance in instances]
