# Espoo Progressive Validation Test Suite

This directory contains the comprehensive validation test suite for Espoo expansion, implementing the progressive validation strategy as specified in the requirements.

## Overview

The Espoo validation suite follows a 4-step progressive approach:

1. **Bug Prevention Tests** - Mandatory comprehensive testing before expensive operations
2. **Step 1: 10 Samples** - Proof of concept validation (≥95% match rate)
3. **Step 2: 100 Samples** - Medium scale validation with geospatial integration (≥98% match rate)
4. **Step 3: Full Scale** - Production readiness validation (≥99.40% match rate)

## Requirements Addressed

- **5.1**: Progressive validation strategy (10 → 100 → full scale)
- **5.2**: Bug prevention tests for all Espoo operations
- **5.3**: Comprehensive quality metrics tracking
- **5.4**: Performance benchmarks and production readiness assessment

## Test Files

### Core Validation Tests

- `test_espoo_bug_prevention.py` - Comprehensive bug prevention before expensive operations
- `test_espoo_step1_10_samples.py` - Step 1: 10 sample listings validation
- `test_espoo_step2_100_samples.py` - Step 2: 100 sample listings with geospatial integration
- `test_espoo_step3_full_scale.py` - Step 3: Full-scale production validation

### Test Runners

- `run_espoo_validation_suite.py` - Complete suite orchestrator with comprehensive reporting
- `../run_espoo_validation.py` - Simple command-line runner for individual tests

## Usage

### Quick Start

```bash
# Run complete validation suite
python run_espoo_validation.py

# Run individual test steps
python run_espoo_validation.py bug-prevention
python run_espoo_validation.py step1
python run_espoo_validation.py step2
python run_espoo_validation.py step3
```

### Using pytest directly

```bash
# Run bug prevention tests (mandatory first step)
uv run python -m pytest tests/validation/test_espoo_bug_prevention.py -v

# Run progressive validation steps
uv run python -m pytest tests/validation/test_espoo_step1_10_samples.py -v
uv run python -m pytest tests/validation/test_espoo_step2_100_samples.py -v
uv run python -m pytest tests/validation/test_espoo_step3_full_scale.py -v

# Run complete suite with orchestrator
uv run python tests/validation/run_espoo_validation_suite.py
```

## Test Structure

### Bug Prevention Tests (`test_espoo_bug_prevention.py`)

**Purpose**: Comprehensive validation before expensive operations (>10 minutes)

**Tests Include**:
- Database connectivity and schema validation
- Espoo configuration integrity
- Data availability and quality assessment
- OSM buildings data integrity
- Coordinate validation functions
- Spatial operations functionality
- Performance baseline with small sample
- Error handling robustness
- Memory usage monitoring

**Success Criteria**: All tests must pass before proceeding to expensive operations

### Step 1: 10 Samples (`test_espoo_step1_10_samples.py`)

**Purpose**: Proof of concept validation with minimal resource usage

**Tests Include**:
- Package import validation
- Database connection testing
- Sample listings loading (10 listings)
- Basic geospatial integration
- Quality metrics tracking
- Validation report generation

**Success Criteria**: ≥95% match rate
**Expected Runtime**: <5 minutes

### Step 2: 100 Samples (`test_espoo_step2_100_samples.py`)

**Purpose**: Medium-scale validation with comprehensive geospatial integration

**Tests Include**:
- Prerequisites validation (Step 1 passed)
- OSM buildings loading and filtering
- Enhanced spatial matching with parallel processing
- Performance benchmarking
- Comprehensive quality metrics
- Advanced validation reporting

**Success Criteria**: ≥98% match rate
**Expected Runtime**: 10-30 minutes

### Step 3: Full Scale (`test_espoo_step3_full_scale.py`)

**Purpose**: Production readiness validation with all available data

**Tests Include**:
- Prerequisites validation (Steps 1 & 2 passed)
- Memory-efficient data loading
- Optimized OSM buildings processing
- Production-scale spatial matching
- Advanced analytics and insights
- Comprehensive production metrics
- Production validation reporting

**Success Criteria**: ≥99.40% match rate
**Expected Runtime**: 30 minutes - 2 hours (depending on dataset size)

## Output Structure

All validation outputs are saved to `output/validation/espoo/`:

```
output/validation/espoo/
├── espoo_bug_prevention_report_YYYYMMDD_HHMMSS.json
├── espoo_step1_metrics_YYYYMMDD_HHMMSS.json
├── espoo_step1_report_YYYYMMDD_HHMMSS.html
├── espoo_step2_metrics_YYYYMMDD_HHMMSS.json
├── espoo_step2_report_YYYYMMDD_HHMMSS.html
├── espoo_step3_production_metrics_YYYYMMDD_HHMMSS.json
├── espoo_step3_production_report_YYYYMMDD_HHMMSS.html
└── espoo_validation_suite_report_YYYYMMDD_HHMMSS.html
```

## Quality Gates

### Step 1 Quality Gates
- ≥95% match rate for coordinate bounds validation
- All package imports successful
- Database connectivity verified
- Basic spatial operations functional

### Step 2 Quality Gates
- ≥98% match rate for OSM building footprint matching
- Performance: ≥0.5 listings/second processing rate
- Memory usage within acceptable limits
- Parallel processing functional

### Step 3 Quality Gates
- ≥99.40% match rate for production readiness
- Performance: ≥1.0 listings/second processing rate
- Processing time: <2 hours for full dataset
- Memory usage: <8GB peak usage
- Quality grade: A or B+ minimum

## Performance Benchmarks

### Expected Performance Targets

| Test Step | Sample Size | Match Rate | Processing Rate | Max Time |
|-----------|-------------|------------|-----------------|----------|
| Step 1    | 10          | ≥95%       | Any             | 5 min    |
| Step 2    | 100         | ≥98%       | ≥0.5/sec        | 30 min   |
| Step 3    | All         | ≥99.40%    | ≥1.0/sec        | 2 hours  |

### System Requirements

- **Memory**: Minimum 4GB RAM, recommended 8GB+
- **CPU**: Multi-core recommended for parallel processing
- **Storage**: Sufficient space for OSM buildings data and outputs
- **Python**: 3.9+ with required packages (see pyproject.toml)

## Error Handling

### Common Issues and Solutions

1. **Database Connection Failures**
   - Verify `data/real_estate.duckdb` exists and is accessible
   - Check database schema with bug prevention tests

2. **OSM Buildings Data Missing**
   - Ensure `data/helsinki_buildings_20250711_041142.geojson` exists
   - Verify file is not corrupted and contains valid GeoJSON

3. **Configuration Issues**
   - Validate `config/config.json` has proper Espoo configuration
   - Check coordinate bounds and geospatial sources

4. **Memory Issues**
   - Reduce chunk size in Step 3 if memory limited
   - Monitor memory usage with system tools

5. **Performance Issues**
   - Reduce max_workers if CPU limited
   - Check for competing processes during validation

## Integration with Development Workflow

### Git Workflow Integration

Each validation step should end with a git commit:

```bash
# After successful validation
git add .
git commit -m "feat(validation): complete Espoo Step X validation with Y% match rate"
```

### Memory Bank Updates

Significant validation results should be documented in the memory bank:

- Update `memory-bank/progress.md` with validation milestones
- Document any issues or insights in `memory-bank/activeContext.md`

### Continuous Integration

The validation suite can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run Espoo Validation
  run: |
    uv run python run_espoo_validation.py bug-prevention
    uv run python run_espoo_validation.py step1
```

## Troubleshooting

### Debug Mode

Run tests with additional debugging:

```bash
# Verbose output with full traceback
uv run python -m pytest tests/validation/test_espoo_step1_10_samples.py -v -s --tb=long

# Run with Python debugging
python -m pdb tests/validation/test_espoo_step1_10_samples.py
```

### Log Analysis

Check logs for detailed execution information:

```bash
# View recent scraper logs
tail -f logs/scraper_$(date +%Y-%m-%d).log

# Check validation outputs
ls -la output/validation/espoo/
```

### Manual Verification

For debugging specific issues:

```python
# Quick database check
import duckdb
conn = duckdb.connect("data/real_estate.duckdb")
print(conn.execute("SELECT COUNT(*) FROM listings WHERE city = 'Espoo'").fetchone())
```

## Contributing

When adding new validation tests:

1. Follow the existing test structure and naming conventions
2. Include comprehensive docstrings and comments
3. Add appropriate success criteria and quality gates
4. Update this README with new test information
5. Ensure tests follow the progressive validation strategy

## Support

For issues with the validation suite:

1. Check this README for common solutions
2. Review test output and error messages
3. Run bug prevention tests to identify system issues
4. Check system requirements and dependencies
5. Consult the main project documentation

---

**Note**: This validation suite is designed to ensure high-quality Espoo expansion with comprehensive testing at each stage. Always run bug prevention tests before expensive operations, and address any failures before proceeding to the next validation step.